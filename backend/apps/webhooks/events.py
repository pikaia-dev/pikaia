"""
Webhook Event Catalog - Single source of truth for available webhook events.

This module defines all events that can be subscribed to via webhooks.
The Lambda dispatcher and UI both use this catalog.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WebhookEventType:
    """Definition of a webhook event type."""

    type: str
    description: str
    category: str
    payload_example: dict


# All available webhook events
# Organized by category for easier navigation
WEBHOOK_EVENTS: dict[str, WebhookEventType] = {}


def _register(event: WebhookEventType) -> WebhookEventType:
    """Register an event type in the catalog."""
    WEBHOOK_EVENTS[event.type] = event
    return event


# =============================================================================
# Member Events
# =============================================================================

MEMBER_CREATED = _register(
    WebhookEventType(
        type="member.created",
        description="Triggered when a new member joins the organization",
        category="member",
        payload_example={
            "member_id": "mbr_01HN...",
            "email": "jane@example.com",
            "name": "Jane Doe",
            "role": "member",
        },
    )
)

MEMBER_UPDATED = _register(
    WebhookEventType(
        type="member.updated",
        description="Triggered when a member's profile is updated",
        category="member",
        payload_example={
            "member_id": "mbr_01HN...",
            "email": "jane@example.com",
            "name": "Jane Smith",
            "changes": ["name"],
        },
    )
)

MEMBER_DELETED = _register(
    WebhookEventType(
        type="member.deleted",
        description="Triggered when a member is removed from the organization",
        category="member",
        payload_example={
            "member_id": "mbr_01HN...",
            "email": "jane@example.com",
            "removed_by": "admin@example.com",
        },
    )
)

MEMBER_ROLE_CHANGED = _register(
    WebhookEventType(
        type="member.role_changed",
        description="Triggered when a member's role is changed",
        category="member",
        payload_example={
            "member_id": "mbr_01HN...",
            "email": "jane@example.com",
            "old_role": "member",
            "new_role": "admin",
        },
    )
)

MEMBER_INVITED = _register(
    WebhookEventType(
        type="member.invited",
        description="Triggered when a new member is invited to the organization",
        category="member",
        payload_example={
            "member_id": "mbr_01HN...",
            "email": "newuser@example.com",
            "invited_by": "admin@example.com",
            "role": "member",
        },
    )
)

# =============================================================================
# Organization Events
# =============================================================================

ORGANIZATION_UPDATED = _register(
    WebhookEventType(
        type="organization.updated",
        description="Triggered when organization settings are changed",
        category="organization",
        payload_example={
            "organization_id": "org_01HN...",
            "changes": ["name", "slug"],
        },
    )
)

# =============================================================================
# Billing Events
# =============================================================================

BILLING_SUBSCRIPTION_CREATED = _register(
    WebhookEventType(
        type="billing.subscription_created",
        description="Triggered when a new subscription is started",
        category="billing",
        payload_example={
            "subscription_id": "sub_01HN...",
            "plan": "pro",
            "status": "active",
            "seats": 5,
        },
    )
)

BILLING_SUBSCRIPTION_UPDATED = _register(
    WebhookEventType(
        type="billing.subscription_updated",
        description="Triggered when a subscription is changed (plan, seats, etc.)",
        category="billing",
        payload_example={
            "subscription_id": "sub_01HN...",
            "plan": "enterprise",
            "status": "active",
            "seats": 25,
            "changes": ["plan", "seats"],
        },
    )
)

BILLING_SUBSCRIPTION_CANCELED = _register(
    WebhookEventType(
        type="billing.subscription_canceled",
        description="Triggered when a subscription is canceled",
        category="billing",
        payload_example={
            "subscription_id": "sub_01HN...",
            "plan": "pro",
            "canceled_at": "2024-01-15T10:30:00Z",
            "ends_at": "2024-02-15T10:30:00Z",
        },
    )
)

BILLING_PAYMENT_SUCCEEDED = _register(
    WebhookEventType(
        type="billing.payment_succeeded",
        description="Triggered when a payment is successfully processed",
        category="billing",
        payload_example={
            "payment_id": "pay_01HN...",
            "amount_cents": 9900,
            "currency": "usd",
            "invoice_id": "inv_01HN...",
        },
    )
)

BILLING_PAYMENT_FAILED = _register(
    WebhookEventType(
        type="billing.payment_failed",
        description="Triggered when a payment fails",
        category="billing",
        payload_example={
            "payment_id": "pay_01HN...",
            "amount_cents": 9900,
            "currency": "usd",
            "failure_reason": "card_declined",
        },
    )
)


# =============================================================================
# Helper Functions
# =============================================================================


def get_event_types() -> list[WebhookEventType]:
    """Get all registered event types."""
    return list(WEBHOOK_EVENTS.values())


def get_event_type(event_type: str) -> WebhookEventType | None:
    """Get a specific event type by name."""
    return WEBHOOK_EVENTS.get(event_type)


def get_categories() -> list[str]:
    """Get all unique event categories."""
    return sorted({e.category for e in WEBHOOK_EVENTS.values()})


def get_events_by_category(category: str) -> list[WebhookEventType]:
    """Get all events in a specific category."""
    return [e for e in WEBHOOK_EVENTS.values() if e.category == category]


def is_valid_event_type(event_type: str) -> bool:
    """Check if an event type is valid (exact match or wildcard)."""
    if event_type in WEBHOOK_EVENTS:
        return True

    # Check wildcard patterns like "member.*"
    if event_type.endswith(".*"):
        prefix = event_type[:-2]
        return any(e.type.startswith(f"{prefix}.") for e in WEBHOOK_EVENTS.values())

    return False


def matches_subscription(event_type: str, subscribed_events: list[str]) -> bool:
    """
    Check if an event type matches any of the subscribed event patterns.

    Supports exact matches and wildcards (e.g., "member.*" matches "member.created").
    """
    for pattern in subscribed_events:
        if pattern == event_type:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            if event_type.startswith(f"{prefix}."):
                return True
    return False
