"""
Events models - transactional outbox for guaranteed event delivery.
"""

import uuid

from django.db import models
from django.utils import timezone


class OutboxEvent(models.Model):
    """
    Transactional outbox for guaranteed event delivery.

    Events are persisted atomically with business data, then published
    by a background worker. This ensures events are never lost even if
    publishing fails.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"

    # Primary key - BigAutoField for B-tree locality on write-heavy table
    id = models.BigAutoField(primary_key=True)

    # Idempotency key - consumers use this to dedupe (UUIDv4 is fine here)
    event_id = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        db_index=True,
        help_text="Unique event identifier for consumer idempotency",
    )

    # Event identity
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Event type, e.g. 'member.invited'",
    )
    aggregate_type = models.CharField(
        max_length=50,
        help_text="Entity type, e.g. 'member'",
    )
    aggregate_id = models.CharField(
        max_length=100,
        help_text="Entity ID, e.g. 'mbr_01HN...'",
    )
    organization_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Tenant organization ID",
    )
    schema_version = models.PositiveIntegerField(
        default=1,
        help_text="Payload schema version for evolution",
    )

    # Full event payload (JSON)
    payload = models.JSONField(
        help_text="Complete event data including actor, data, correlation_id, etc.",
    )

    # Publishing lifecycle
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the event was successfully published",
    )

    # Retry tracking
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of publish attempts",
    )
    next_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When to retry publishing (for exponential backoff)",
    )
    last_error = models.TextField(
        blank=True,
        help_text="Last error message from failed publish attempt",
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            # Publisher query: find events ready to publish
            models.Index(fields=["status", "next_attempt_at"]),
            # Debug: find events for an aggregate
            models.Index(fields=["aggregate_type", "aggregate_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.status})"

    def mark_published(self) -> None:
        """Mark event as successfully published."""
        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at"])

    def mark_failed(self, error: str, max_attempts: int = 10) -> None:
        """
        Mark event as failed and schedule retry with exponential backoff.

        After max_attempts, status becomes FAILED permanently.
        """
        self.attempts += 1
        self.last_error = error

        if self.attempts >= max_attempts:
            self.status = self.Status.FAILED
            self.next_attempt_at = None
        else:
            # Exponential backoff: 1s, 2s, 4s, 8s... up to 5 minutes
            delay_seconds = min(2**self.attempts, 300)
            self.next_attempt_at = timezone.now() + timezone.timedelta(
                seconds=delay_seconds
            )

        self.save(update_fields=["attempts", "last_error", "status", "next_attempt_at"])


class AuditLog(models.Model):
    """
    Permanent audit log for compliance and debugging.

    Unlike OutboxEvent (transient), AuditLog entries are retained long-term.
    Contains richer context (diffs, IP, user-agent) than domain events.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # What happened
    action = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Action type, e.g. 'member.role_changed'",
    )
    aggregate_type = models.CharField(max_length=50)
    aggregate_id = models.CharField(max_length=100)
    organization_id = models.CharField(max_length=100, db_index=True)

    # Who did it
    actor_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="User or system ID that performed the action",
    )
    actor_email = models.EmailField(
        blank=True,
        help_text="Actor email (denormalized for display)",
    )

    # Context
    correlation_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Request trace ID for correlation",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address",
    )
    user_agent = models.TextField(
        blank=True,
        help_text="Client user agent string",
    )

    # Changes (optional field-level diff)
    diff = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field-level changes: {'old': {...}, 'new': {...}}",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context (method, path, etc.)",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "created_at"]),
            models.Index(fields=["aggregate_type", "aggregate_id"]),
            models.Index(fields=["actor_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} by {self.actor_email or self.actor_id}"
