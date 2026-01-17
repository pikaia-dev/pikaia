"""
Webhook API schemas (Pydantic models for request/response).
"""

from datetime import datetime

from ninja import Schema
from pydantic import Field, field_validator

from .events import is_valid_event_type

# =============================================================================
# Request Schemas
# =============================================================================


class WebhookEndpointCreate(Schema):
    """Schema for creating a webhook endpoint."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    url: str = Field(..., min_length=1, max_length=2048)
    events: list[str] = Field(..., min_length=1)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is HTTPS."""
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        """Ensure all events are valid."""
        for event in v:
            if not is_valid_event_type(event):
                raise ValueError(f"Invalid event type: {event}")
        return v


class WebhookEndpointUpdate(Schema):
    """Schema for updating a webhook endpoint."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    events: list[str] | None = Field(default=None, min_length=1)
    active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """Ensure URL is HTTPS."""
        if v is not None and not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        """Ensure all events are valid."""
        if v is not None:
            for event in v:
                if not is_valid_event_type(event):
                    raise ValueError(f"Invalid event type: {event}")
        return v


class WebhookTestRequest(Schema):
    """Schema for sending a test webhook."""

    event_type: str

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Ensure event type is valid (no wildcards for test)."""
        if v.endswith(".*"):
            raise ValueError("Cannot use wildcard for test event")
        if not is_valid_event_type(v):
            raise ValueError(f"Invalid event type: {v}")
        return v


# =============================================================================
# Response Schemas
# =============================================================================


class WebhookEndpointResponse(Schema):
    """Schema for webhook endpoint in responses."""

    id: str
    name: str
    description: str
    url: str
    events: list[str]
    active: bool
    last_delivery_status: str
    last_delivery_at: datetime | None
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime


class WebhookEndpointWithSecretResponse(WebhookEndpointResponse):
    """Schema for webhook endpoint response including secret (only on creation)."""

    secret: str


class WebhookEndpointListResponse(Schema):
    """Schema for listing webhook endpoints."""

    endpoints: list[WebhookEndpointResponse]


class WebhookDeliveryResponse(Schema):
    """Schema for webhook delivery in responses."""

    id: str
    event_id: str
    event_type: str
    status: str
    error_type: str
    http_status: int | None
    duration_ms: int | None
    response_snippet: str
    attempt_number: int
    attempted_at: datetime | None
    created_at: datetime


class WebhookDeliveryListResponse(Schema):
    """Schema for listing webhook deliveries."""

    deliveries: list[WebhookDeliveryResponse]


class WebhookTestResponse(Schema):
    """Schema for test webhook response."""

    success: bool
    http_status: int | None
    duration_ms: int | None
    signature: str
    response_snippet: str
    error_message: str = ""


class WebhookEventTypeResponse(Schema):
    """Schema for a single event type."""

    type: str
    description: str
    category: str
    payload_example: dict


class WebhookEventListResponse(Schema):
    """Schema for listing available events."""

    events: list[WebhookEventTypeResponse]


# =============================================================================
# Webhook Payload Schema (sent to customer endpoints)
# =============================================================================


class WebhookPayload(Schema):
    """
    Schema for the payload sent to customer webhook endpoints.

    This is what customers receive in the POST body.
    """

    id: str = Field(..., description="Unique event ID for idempotency")
    spec_version: str = Field(default="1.0", description="Payload schema version")
    type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="When the event occurred")
    organization_id: str = Field(..., description="Organization this event belongs to")
    data: dict = Field(..., description="Event-specific payload data")
