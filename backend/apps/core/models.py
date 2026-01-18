"""
Core models - shared base classes and utilities.
"""

from django.db import models


class ProcessedWebhook(models.Model):
    """
    Tracks processed webhook events for idempotency.

    Prevents duplicate processing when webhook providers
    deliver the same event multiple times (at-least-once delivery).
    """

    source = models.CharField(max_length=50, db_index=True)
    event_id = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "event_id"], name="unique_webhook_event"),
        ]
        indexes = [
            models.Index(fields=["processed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.event_id}"


class TimestampedModel(models.Model):
    """
    Abstract base model with created_at/updated_at timestamps.

    All business entities should inherit from this or TenantScopedModel.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimestampedModel):
    """
    Abstract base model for all organization-scoped entities.

    Provides:
    - Automatic organization FK
    - Timestamps from TimestampedModel

    Usage:
        class Project(TenantScopedModel):
            name = models.CharField(max_length=255)
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
    )

    class Meta:
        abstract = True
