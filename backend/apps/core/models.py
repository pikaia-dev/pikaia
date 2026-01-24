"""
Core models - shared base classes and utilities.
"""

from __future__ import annotations

from typing import Self

from django.db import models
from django.utils import timezone


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


class SoftDeleteQuerySet(models.QuerySet):
    """
    QuerySet that supports soft delete operations.

    Provides bulk soft delete via .delete() and explicit .hard_delete()
    for permanent removal (e.g., GDPR compliance).
    """

    def delete(self) -> tuple[int, dict[str, int]]:
        """
        Soft delete all records in queryset.

        Returns tuple of (count, {model_label: count}) to match Django's
        delete() signature.
        """
        count = self.update(deleted_at=timezone.now())
        return count, {self.model._meta.label: count}

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """Permanently delete records. Use for GDPR 'right to be forgotten'."""
        return super().delete()

    def alive(self) -> Self:
        """Filter to only non-deleted records."""
        return self.filter(deleted_at__isnull=True)

    def dead(self) -> Self:
        """Filter to only soft-deleted records."""
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    """
    Default manager that excludes soft-deleted records.

    Use as `objects` manager on models inheriting SoftDeleteMixin.
    """

    def get_queryset(self) -> SoftDeleteQuerySet:
        """Return only active (non-deleted) records."""
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteAllManager(models.Manager):
    """
    Manager that includes all records, including soft-deleted.

    Use as `all_objects` for admin views, data recovery, or audit.
    Provides .alive() and .dead() for filtering.
    """

    def get_queryset(self) -> SoftDeleteQuerySet:
        """Return all records including soft-deleted."""
        return SoftDeleteQuerySet(self.model, using=self._db)

    def dead(self) -> SoftDeleteQuerySet:
        """Return only soft-deleted records."""
        return self.get_queryset().dead()


class SoftDeleteMixin(models.Model):
    """
    Mixin providing soft delete functionality.

    Adds:
    - deleted_at field (NULL = active, timestamp = deleted)
    - is_deleted property
    - soft_delete() / restore() / hard_delete() methods

    Usage:
        class MyModel(SoftDeleteMixin, TimestampedModel):
            objects = SoftDeleteManager()
            all_objects = SoftDeleteAllManager()

    Important: Place SoftDeleteMixin BEFORE TimestampedModel in MRO
    so that soft_delete() can update the updated_at field.
    """

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Soft delete timestamp. NULL = active record.",
    )

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self, *, update_timestamp: bool = True) -> None:
        """
        Soft delete this record by setting deleted_at timestamp.

        Args:
            update_timestamp: If True and model has updated_at field,
                              also update it. Defaults to True.
        """
        self.deleted_at = timezone.now()
        update_fields = ["deleted_at"]

        if update_timestamp and hasattr(self, "updated_at"):
            update_fields.append("updated_at")

        self.save(update_fields=update_fields)

    def restore(self, *, update_timestamp: bool = True) -> None:
        """
        Restore a soft-deleted record.

        Args:
            update_timestamp: If True and model has updated_at field,
                              also update it. Defaults to True.
        """
        self.deleted_at = None
        update_fields = ["deleted_at"]

        if update_timestamp and hasattr(self, "updated_at"):
            update_fields.append("updated_at")

        self.save(update_fields=update_fields)

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """
        Permanently delete this record from the database.

        Use for GDPR 'right to be forgotten' compliance or when
        soft delete recovery is not needed.
        """
        return super().delete()


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
