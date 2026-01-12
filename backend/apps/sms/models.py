"""
OTP verification models.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class OTPVerification(models.Model):
    """
    Stores OTP codes for phone verification.

    OTPs are single-use and expire after a configurable time.
    Rate limiting is enforced via attempt tracking.
    """

    class Purpose(models.TextChoices):
        """Purpose of the OTP verification."""

        PHONE_VERIFY = "phone_verify", "Phone Verification"
        LOGIN = "login", "Login"

    # Who is verifying
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="otp_verifications",
        null=True,
        blank=True,
        help_text="User requesting verification (null for login flow)",
    )
    phone_number = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Phone number in E.164 format",
    )

    # OTP details
    code = models.CharField(max_length=10, help_text="The OTP code")
    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
        default=Purpose.PHONE_VERIFY,
    )

    # Status tracking
    is_verified = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of verification attempts",
    )
    max_attempts = models.PositiveSmallIntegerField(
        default=5,
        help_text="Maximum allowed attempts",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    # AWS tracking
    aws_message_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="AWS SMS message ID for tracking",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number", "purpose", "is_verified"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"OTP for {self.phone_number[-4:]} ({self.purpose})"

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Set expiration time on creation."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(
                minutes=settings.AWS_SMS_OTP_EXPIRY_MINUTES
            )
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        """Check if the OTP has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if OTP can still be used (not expired, not verified, attempts remaining)."""
        return (
            not self.is_expired
            and not self.is_verified
            and self.attempts < self.max_attempts
        )

    def increment_attempts(self) -> None:
        """Increment the attempt counter."""
        self.attempts += 1
        self.save(update_fields=["attempts"])

    def mark_verified(self) -> None:
        """Mark the OTP as successfully verified."""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_verified", "verified_at"])
