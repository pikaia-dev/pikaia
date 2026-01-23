"""
Device models - mobile device linking and management.
"""

import uuid

from django.db import models
from django.utils import timezone

from apps.core.models import TimestampedModel


class DeviceManager(models.Manager["Device"]):
    """Custom manager that excludes revoked devices by default."""

    def get_queryset(self) -> models.QuerySet["Device"]:
        """Return only active (non-revoked) devices."""
        return super().get_queryset().filter(revoked_at__isnull=True)


class DeviceAllManager(models.Manager["Device"]):
    """Manager that includes all devices, including revoked ones."""

    pass


class Device(TimestampedModel):
    """
    Linked mobile device.

    Represents a mobile device that has been linked to a user's account
    via QR code scanning.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="devices",
        help_text="User who owns this device",
    )
    device_uuid = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique device identifier from iOS Keychain / Android",
    )
    name = models.CharField(
        max_length=100,
        help_text="Device name (e.g., 'iPhone 15 Pro')",
    )
    platform = models.CharField(
        max_length=20,
        help_text="Platform identifier (e.g., 'ios', 'android')",
    )
    os_version = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Operating system version (e.g., '17.2')",
    )
    app_version = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="App version (e.g., '1.0.0')",
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when device was revoked. NULL = active.",
    )

    objects = DeviceManager()
    all_objects = DeviceAllManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
        ]

    def __str__(self) -> str:
        status = " (revoked)" if self.is_revoked else ""
        return f"{self.name} - {self.user.email}{status}"

    @property
    def is_revoked(self) -> bool:
        """Check if device is revoked."""
        return self.revoked_at is not None

    def revoke(self) -> None:
        """Revoke this device by setting revoked_at timestamp."""
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at", "updated_at"])


class DeviceLinkToken(models.Model):
    """
    One-time token for QR code device linking.

    Generated when user requests to link a mobile device.
    Contains a JWT that the mobile app scans and uses to complete linking.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="device_link_tokens",
        help_text="User who initiated the link",
    )
    member = models.ForeignKey(
        "accounts.Member",
        on_delete=models.CASCADE,
        related_name="device_link_tokens",
        help_text="Member context for initial session",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="device_link_tokens",
        help_text="Organization context for initial session",
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 hash of the JWT token",
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Token expiration timestamp",
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when token was used. NULL = unused.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "expires_at"]),
        ]

    def __str__(self) -> str:
        status = "used" if self.is_used else ("expired" if self.is_expired else "valid")
        return f"LinkToken {self.id} ({status})"

    @property
    def is_used(self) -> bool:
        """Check if token has been used."""
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not used and not expired)."""
        return not self.is_used and not self.is_expired

    def mark_used(self) -> None:
        """Mark token as used."""
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
