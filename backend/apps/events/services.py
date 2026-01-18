"""
Event services - publishing events via transactional outbox.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from apps.accounts.models import User

import structlog
from django.db import models

from apps.core.logging import get_logger
from apps.events.models import AuditLog, OutboxEvent
from apps.events.schemas import MAX_PAYLOAD_SIZE_BYTES, ActorSchema, EventEnvelope

logger = get_logger(__name__)


# Context variable for correlation ID (set by middleware)
_correlation_id: UUID | None = None


def set_correlation_id(correlation_id: UUID | None) -> None:
    """Set correlation ID for current request context."""
    global _correlation_id
    _correlation_id = correlation_id


def get_correlation_id() -> UUID | None:
    """Get correlation ID for current request context."""
    return _correlation_id


def publish_event(
    event_type: str,
    aggregate: models.Model,
    data: dict[str, Any],
    actor: "User | None" = None,
    organization_id: str | None = None,
    schema_version: int = 1,
) -> OutboxEvent:
    """
    Publish an event via the transactional outbox.

    Call this inside a transaction.atomic() block to ensure the event
    is persisted atomically with your business data.

    Args:
        event_type: Event type, e.g. 'member.invited'
        aggregate: The model instance this event is about
        data: Event-specific payload data
        actor: User who caused the event (None for system events)
        organization_id: Organization ID (extracted from aggregate if not provided)
        schema_version: Payload schema version (default 1)

    Returns:
        The created OutboxEvent instance

    Raises:
        ValueError: If payload exceeds EventBridge size limit (256 KB)
    """
    # Determine aggregate info
    aggregate_type = aggregate.__class__.__name__.lower()
    aggregate_id = str(aggregate.pk)

    # Determine organization_id from aggregate if not provided
    if organization_id is None:
        if hasattr(aggregate, "organization_id"):
            organization_id = str(aggregate.organization_id)
        elif hasattr(aggregate, "organization"):
            organization_id = str(aggregate.organization.pk)
        elif aggregate_type == "organization":
            organization_id = str(aggregate.pk)
        else:
            raise ValueError(
                f"Cannot determine organization_id for {aggregate_type}. "
                "Pass organization_id explicitly."
            )

    # Build actor
    if actor is not None:
        actor_schema = ActorSchema(
            type="user",
            id=str(actor.pk),
            email=actor.email,
        )
    else:
        actor_schema = ActorSchema(type="system", id="system")

    # Get request context from structlog contextvars (set by middleware)
    ctx = structlog.contextvars.get_contextvars()
    request_context = {
        "ip_address": ctx.get("request.ip_address"),
        "user_agent": ctx.get("request.user_agent", ""),
    }

    # Merge request context with event data (explicit data takes precedence)
    enriched_data = {**request_context, **data}

    # Build event envelope
    event_id = uuid4()
    envelope = EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        schema_version=schema_version,
        occurred_at=datetime.now(UTC),
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        organization_id=organization_id,
        correlation_id=get_correlation_id(),
        actor=actor_schema,
        data=enriched_data,
    )

    # Validate payload size
    payload_json = envelope.model_dump_json()
    if len(payload_json.encode("utf-8")) > MAX_PAYLOAD_SIZE_BYTES:
        raise ValueError(
            f"Event payload exceeds {MAX_PAYLOAD_SIZE_BYTES} bytes limit. "
            "Consider storing large data elsewhere and referencing it."
        )

    # Create outbox event
    outbox_event = OutboxEvent.objects.create(
        event_id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        organization_id=organization_id,
        schema_version=schema_version,
        payload=envelope.model_dump(mode="json"),
    )

    logger.debug("outbox_event_created", event_type=event_type, event_id=str(event_id))
    return outbox_event


def create_audit_log(
    action: str,
    aggregate: models.Model,
    actor: "User | None" = None,
    organization_id: str | None = None,
    diff: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """
    Create an audit log entry.

    Unlike events (which are transient), audit logs are retained long-term
    for compliance and debugging.

    Args:
        action: Action type, e.g. 'member.role_changed'
        aggregate: The model instance this action affected
        actor: User who performed the action
        organization_id: Organization ID
        diff: Field-level changes {'old': {...}, 'new': {...}}
        metadata: Additional context
        ip_address: Client IP
        user_agent: Client user agent

    Returns:
        The created AuditLog instance
    """
    aggregate_type = aggregate.__class__.__name__.lower()
    aggregate_id = str(aggregate.pk)

    # Determine organization_id
    if organization_id is None:
        if hasattr(aggregate, "organization_id"):
            organization_id = str(aggregate.organization_id)
        elif hasattr(aggregate, "organization"):
            organization_id = str(aggregate.organization.pk)
        elif aggregate_type == "organization":
            organization_id = str(aggregate.pk)
        else:
            organization_id = ""

    return AuditLog.objects.create(
        action=action,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        organization_id=organization_id,
        actor_id=str(actor.pk) if actor else "system",
        actor_email=actor.email if actor else "",
        correlation_id=get_correlation_id(),
        ip_address=ip_address,
        user_agent=user_agent or "",
        diff=diff or {},
        metadata=metadata or {},
    )
