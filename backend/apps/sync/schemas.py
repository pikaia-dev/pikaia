"""
Pydantic schemas for sync API.
"""

from datetime import datetime, timedelta
from typing import Literal

from django.utils import timezone
from ninja import Field, Schema
from pydantic import field_validator

# Type alias for sync operation status
SyncStatus = Literal["applied", "rejected", "conflict", "duplicate"]

# Maximum allowed drift between client_timestamp and server time.
# Timestamps beyond this window are rejected to prevent clock skew exploits
# against LWW conflict resolution.
MAX_CLIENT_TIMESTAMP_DRIFT = timedelta(hours=24)


class SyncOperationIn(Schema):
    """Input schema for a single sync operation."""

    idempotency_key: str = Field(..., min_length=1, max_length=64)
    entity_type: str = Field(..., min_length=1, max_length=64)
    entity_id: str = Field(..., min_length=1, max_length=36)
    intent: Literal["create", "update", "delete"]
    client_timestamp: datetime
    base_version: int | None = None  # For optimistic concurrency
    retry_count: int = 0  # How many times client retried this op

    # PATCH semantics for 'update' intent:
    # - data contains ONLY changed fields
    # - Omitted fields are NOT overwritten on server
    # - For 'create': data is complete entity
    # - For 'delete': data is ignored (can be empty {})
    data: dict

    @field_validator("client_timestamp")
    @classmethod
    def validate_client_timestamp_range(cls, v: datetime) -> datetime:
        now = timezone.now()
        drift = abs((v - now).total_seconds())
        max_drift_seconds = MAX_CLIENT_TIMESTAMP_DRIFT.total_seconds()
        if drift > max_drift_seconds:
            raise ValueError(
                f"client_timestamp is too far from server time "
                f"(drift: {int(drift)}s, max allowed: {int(max_drift_seconds)}s)"
            )
        return v


class SyncPushRequest(Schema):
    """Request schema for push endpoint."""

    operations: list[SyncOperationIn] = Field(..., max_length=100)
    device_id: str = Field(..., min_length=1, max_length=64)


class SyncResultOut(Schema):
    """Result for a single sync operation."""

    idempotency_key: str
    status: SyncStatus
    server_timestamp: datetime
    server_version: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict | None = None  # Structured validation errors
    conflict_data: dict | None = None  # Server state if conflict


class SyncPushResponse(Schema):
    """Response schema for push endpoint."""

    results: list[SyncResultOut]


class SyncPullParams(Schema):
    """Query parameters for pull endpoint."""

    since: str | None = None  # Opaque cursor
    entity_types: str | None = None  # Comma-separated filter
    limit: int = Field(default=100, ge=1, le=500)


class ChangeOut(Schema):
    """A single change in the pull response."""

    entity_type: str
    entity_id: str
    operation: Literal["upsert", "delete"]
    data: dict | None = None  # None for deletes
    version: int
    updated_at: datetime


class SyncPullResponse(Schema):
    """Response schema for pull endpoint."""

    changes: list[ChangeOut]
    cursor: str | None  # Opaque cursor for next page
    has_more: bool
    force_resync: bool = False  # If True, client should do full resync
