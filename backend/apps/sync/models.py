"""
Sync engine models.

Provides base classes for syncable entities and operation logging.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from django.db import models
from uuid6 import uuid7

from apps.core.models import (
    SoftDeleteAllManager,
    SoftDeleteManager,
    SoftDeleteMixin,
    TimestampedModel,
)

if TYPE_CHECKING:
    pass


class FieldLevelLWWMixin(models.Model):
    """
    Mixin for entities using field-level LWW conflict resolution.

    Tracks per-field modification timestamps to enable granular merge.
    """

    class Meta:
        abstract = True

    # Fields to exclude from LWW tracking
    LWW_EXCLUDED_FIELDS: ClassVar[set[str]] = {
        "id",
        "organization",
        "organization_id",
        "created_at",
        "updated_at",
        "deleted_at",
        "sync_version",
        "field_timestamps",
        "last_modified_by",
        "last_modified_by_id",
        "device_id",
    }

    # JSON object mapping field names to ISO timestamps
    # Example: {"name": "2025-01-23T10:00:00Z", "phone": "2025-01-23T09:30:00Z"}
    field_timestamps = models.JSONField(
        default=dict,
        help_text="Per-field modification timestamps for LWW resolution",
    )

    def set_field_timestamp(self, field: str, timestamp: datetime) -> None:
        """Update the timestamp for a single field."""
        self.field_timestamps[field] = timestamp.isoformat()

    def get_field_timestamp(self, field: str) -> datetime | None:
        """Get the timestamp for a field, or None if never set."""
        ts = self.field_timestamps.get(field)
        if ts:
            return datetime.fromisoformat(ts)
        return None

    def update_fields_with_timestamps(
        self,
        updates: dict,
        timestamp: datetime,
    ) -> None:
        """
        Update multiple fields and their timestamps atomically.

        Call this instead of setting fields directly.
        """
        for field, value in updates.items():
            setattr(self, field, value)
            self.set_field_timestamp(field, timestamp)

    @classmethod
    def get_syncable_fields(cls) -> list[str]:
        """Return list of fields that participate in field-level LWW."""
        return [
            f.name
            for f in cls._meta.get_fields()
            if f.concrete
            and getattr(f, "primary_key", False) is False
            and f.name not in cls.LWW_EXCLUDED_FIELDS
        ]


class SyncableModel(SoftDeleteMixin, TimestampedModel):
    """
    Base for all sync-enabled entities.

    Inherits soft-delete behavior from SoftDeleteMixin.
    IMPORTANT: SoftDeleteMixin MUST come before TimestampedModel in MRO
    so that soft_delete() properly updates updated_at timestamp.

    Manager usage:
    - .objects: Excludes deleted records (for normal app queries)
    - .all_objects: Includes deleted records (REQUIRED for sync pull)

    ID Strategy:
    Uses native PostgreSQL UUIDs with UUIDv7 for time-ordered, collision-free
    IDs that work for offline-first clients. UUIDv7 embeds a Unix timestamp
    in the high bits, making IDs naturally sortable by creation time.
    """

    # Managers - follow existing Pikaia pattern
    objects = SoftDeleteManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        abstract = True
        indexes = [
            # Critical for cursor-based pull queries (includes deleted)
            models.Index(fields=["organization", "updated_at", "id"]),
        ]

    # Use UUIDv7 for time-sortable, collision-free IDs
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
    )

    # Sync metadata
    sync_version = models.PositiveBigIntegerField(default=0)
    last_modified_by = models.ForeignKey(
        "accounts.Member",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_modified",
    )
    device_id = models.CharField(max_length=64, null=True, blank=True)

    def save(self, *args, **kwargs):
        """Increment sync version on save."""
        self.sync_version += 1
        super().save(*args, **kwargs)


class SyncOperation(models.Model):
    """
    Append-only log of all sync operations for audit and replay.

    Each operation represents a single client push request.
    """

    class Intent(models.TextChoices):
        CREATE = "create"
        UPDATE = "update"
        DELETE = "delete"

    class Status(models.TextChoices):
        PENDING = "pending"
        APPLIED = "applied"
        REJECTED = "rejected"
        CONFLICT = "conflict"
        DUPLICATE = "duplicate"

    # Idempotency - unique constraint ensures atomic claim pattern
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)

    # Context
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="sync_operations",
    )
    actor = models.ForeignKey(
        "accounts.Member",
        on_delete=models.SET_NULL,
        null=True,
        related_name="sync_operations",
    )
    device_id = models.CharField(max_length=64)

    # Operation details
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=36)
    intent = models.CharField(max_length=16, choices=Intent.choices)

    # Payload & timestamps
    payload = models.JSONField()
    client_timestamp = models.DateTimeField()
    server_timestamp = models.DateTimeField(auto_now_add=True)

    # Resolution
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    resolution_details = models.JSONField(null=True, blank=True)

    # Observability metrics
    drift_ms = models.IntegerField(
        null=True, blank=True, help_text="server_timestamp - client_timestamp in ms"
    )
    conflict_fields = models.JSONField(
        null=True, blank=True, help_text="Fields that had conflicts (for field-level LWW)"
    )
    client_retry_count = models.PositiveSmallIntegerField(
        default=0, help_text="Times client retried this op"
    )

    class Meta:
        indexes = [
            models.Index(fields=["organization", "server_timestamp"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]
        ordering = ["-server_timestamp"]

    def __str__(self) -> str:
        return f"{self.intent} {self.entity_type}:{self.entity_id} ({self.status})"

    def calculate_drift_ms(self) -> int:
        """Calculate drift between client and server timestamps in milliseconds."""
        delta = self.server_timestamp - self.client_timestamp
        return int(delta.total_seconds() * 1000)
