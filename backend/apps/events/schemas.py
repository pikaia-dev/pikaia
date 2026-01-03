"""
Event schemas - Pydantic models for event envelope and validation.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ActorSchema(BaseModel):
    """Who caused the event."""

    type: str = Field(description="Actor type: 'user' or 'system'")
    id: str = Field(description="Actor identifier")
    email: str | None = Field(default=None, description="Actor email if user")


class EventEnvelope(BaseModel):
    """
    Standard event envelope matching events.md specification.

    All events follow this structure for consistency.
    """

    # Identity
    event_id: UUID = Field(description="Unique event ID for idempotency")
    event_type: str = Field(description="Event type, e.g. 'member.invited'")
    schema_version: int = Field(default=1, description="Payload schema version")

    # Timing
    occurred_at: datetime = Field(description="When the event happened (UTC)")

    # Aggregate
    aggregate_id: str = Field(description="Entity ID, e.g. 'mbr_01HN...'")
    aggregate_type: str = Field(description="Entity type, e.g. 'member'")

    # Tenant
    organization_id: str = Field(description="Organization ID for tenant scoping")

    # Tracing
    correlation_id: UUID | None = Field(
        default=None, description="Request trace ID for correlation"
    )

    # Actor
    actor: ActorSchema = Field(description="Who caused the event")

    # Payload
    data: dict[str, Any] = Field(default_factory=dict, description="Event-specific data")


# Maximum payload size for EventBridge (256 KB)
MAX_PAYLOAD_SIZE_BYTES = 256 * 1024
