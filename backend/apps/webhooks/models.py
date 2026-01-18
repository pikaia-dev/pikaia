"""
Webhook models for customer-facing webhook delivery.
"""

import secrets
import uuid
from typing import ClassVar

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone


def generate_webhook_secret() -> str:
    """Generate a secure webhook signing secret."""
    return f"whsec_{secrets.token_urlsafe(32)}"


def generate_webhook_id() -> str:
    """Generate a prefixed webhook endpoint ID."""
    return f"wh_{uuid.uuid4().hex[:24]}"


def generate_delivery_id() -> str:
    """Generate a prefixed delivery ID."""
    return f"del_{uuid.uuid4().hex[:24]}"


class WebhookEndpoint(models.Model):
    """
    A customer-configured webhook endpoint.

    Organizations can create multiple endpoints, each subscribed to
    different event types and receiving signed HTTP POST requests.
    """

    class Source(models.TextChoices):
        """How this endpoint was created."""

        MANUAL = "manual", "Manual (UI/API)"
        ZAPIER = "zapier", "Zapier"
        MAKE = "make", "Make"
        REST_HOOKS = "rest_hooks", "REST Hooks (generic)"

    # Sources that are considered REST Hook subscriptions (not manual)
    REST_HOOK_SOURCES: ClassVar[list[str]] = [
        Source.ZAPIER,
        Source.MAKE,
        Source.REST_HOOKS,
    ]

    id = models.CharField(
        primary_key=True,
        max_length=32,
        default=generate_webhook_id,
        editable=False,
    )

    # Ownership
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_webhook_endpoints",
        help_text="User who created this endpoint",
    )

    # Endpoint configuration
    name = models.CharField(
        max_length=100,
        help_text="Human-readable name for this endpoint",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of what this endpoint is used for",
    )
    url = models.URLField(
        max_length=2048,
        help_text="HTTPS URL to receive webhook events",
    )

    # Event subscriptions - supports wildcards like "member.*"
    events = ArrayField(
        models.CharField(max_length=100),
        help_text="List of event types to receive (supports wildcards like 'member.*')",
    )

    # Source tracking (how this endpoint was created)
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
        help_text="How this endpoint was created (manual, zapier, make, rest_hooks)",
    )

    # Signing secret
    secret = models.CharField(
        max_length=64,
        default=generate_webhook_secret,
        help_text="Secret used to sign webhook payloads (HMAC-SHA256)",
    )

    # Status
    active = models.BooleanField(
        default=True,
        help_text="Whether this endpoint receives events",
    )

    # Delivery tracking (denormalized for quick access)
    last_delivery_status = models.CharField(
        max_length=20,
        blank=True,
        help_text="Status of most recent delivery: success, failure, pending",
    )
    last_delivery_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of most recent delivery attempt",
    )
    consecutive_failures = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive failed deliveries (resets on success)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.url})"

    def regenerate_secret(self) -> str:
        """
        Generate a new signing secret.

        Note: This immediately invalidates the old secret.
        For dual-secret rotation, use the secret rotation service (V2 feature).
        """
        self.secret = generate_webhook_secret()
        self.save(update_fields=["secret", "updated_at"])
        return self.secret

    def record_delivery_success(self) -> None:
        """Update status after successful delivery."""
        self.last_delivery_status = "success"
        self.last_delivery_at = timezone.now()
        self.consecutive_failures = 0
        self.save(
            update_fields=[
                "last_delivery_status",
                "last_delivery_at",
                "consecutive_failures",
                "updated_at",
            ]
        )

    def record_delivery_failure(self) -> None:
        """Update status after failed delivery."""
        self.last_delivery_status = "failure"
        self.last_delivery_at = timezone.now()
        self.consecutive_failures += 1
        self.save(
            update_fields=[
                "last_delivery_status",
                "last_delivery_at",
                "consecutive_failures",
                "updated_at",
            ]
        )


class WebhookDelivery(models.Model):
    """
    Record of a webhook delivery attempt.

    Stores delivery metadata for debugging and observability.
    Avoids storing full payloads to prevent PII retention issues.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"

    class ErrorType(models.TextChoices):
        NONE = "", "None"
        TIMEOUT = "timeout", "Timeout"
        CONNECTION_ERROR = "connection_error", "Connection Error"
        HTTP_ERROR = "http_error", "HTTP Error"
        INVALID_RESPONSE = "invalid_response", "Invalid Response"
        SSL_ERROR = "ssl_error", "SSL Error"

    # Retry configuration
    MAX_ATTEMPTS: ClassVar[int] = 6
    RETRY_DELAYS_SECONDS: ClassVar[list[int]] = [
        0,  # Attempt 1: immediate
        60,  # Attempt 2: 1 minute
        300,  # Attempt 3: 5 minutes
        1800,  # Attempt 4: 30 minutes
        7200,  # Attempt 5: 2 hours
        28800,  # Attempt 6: 8 hours
    ]

    id = models.CharField(
        primary_key=True,
        max_length=32,
        default=generate_delivery_id,
        editable=False,
    )

    # References
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )

    # Event identity (for idempotency)
    event_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Unique event ID (from OutboxEvent.event_id)",
    )
    event_type = models.CharField(
        max_length=100,
        help_text="Event type, e.g. 'member.created'",
    )

    # Endpoint URL snapshot (in case endpoint URL changes)
    url_snapshot = models.URLField(
        max_length=2048,
        help_text="URL at time of delivery (snapshot)",
    )

    # Delivery status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_type = models.CharField(
        max_length=30,
        choices=ErrorType.choices,
        default=ErrorType.NONE,
        blank=True,
    )

    # Response details
    http_status = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="HTTP response status code",
    )
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Request duration in milliseconds",
    )
    response_snippet = models.TextField(
        blank=True,
        max_length=500,
        help_text="First 500 chars of response body (for debugging, no PII)",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if delivery failed",
    )

    # Retry tracking
    attempt_number = models.PositiveSmallIntegerField(
        default=1,
        help_text="Current attempt number (1-6)",
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When to retry (null if no retry scheduled)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    attempted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the delivery was last attempted",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["endpoint", "created_at"]),
            models.Index(fields=["event_id", "endpoint"]),  # Idempotency check
            models.Index(fields=["status", "next_retry_at"]),  # Retry queue
        ]
        # Ensure idempotency: one delivery per event per endpoint
        constraints = [
            models.UniqueConstraint(
                fields=["event_id", "endpoint"],
                name="unique_delivery_per_event_endpoint",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} → {self.endpoint.name} ({self.status})"

    def mark_success(self, http_status: int, duration_ms: int, response_snippet: str = "") -> None:
        """Mark delivery as successful."""
        self.status = self.Status.SUCCESS
        self.http_status = http_status
        self.duration_ms = duration_ms
        self.response_snippet = response_snippet[:500]  # Truncate
        self.attempted_at = timezone.now()
        self.next_retry_at = None
        self.save(
            update_fields=[
                "status",
                "http_status",
                "duration_ms",
                "response_snippet",
                "attempted_at",
                "next_retry_at",
            ]
        )
        self.endpoint.record_delivery_success()

    def mark_failure(
        self,
        error_type: str,
        error_message: str,
        http_status: int | None = None,
        duration_ms: int | None = None,
        response_snippet: str = "",
        terminal: bool = False,
    ) -> None:
        """
        Mark delivery as failed and schedule retry if applicable.

        Args:
            error_type: Type of error (timeout, connection_error, etc.)
            error_message: Human-readable error message
            http_status: HTTP status code if available
            duration_ms: Request duration if available
            response_snippet: Response body snippet if available
            terminal: If True, don't retry (e.g., 410 Gone)
        """
        self.error_type = error_type
        self.error_message = error_message
        self.http_status = http_status
        self.duration_ms = duration_ms
        self.response_snippet = response_snippet[:500] if response_snippet else ""
        self.attempted_at = timezone.now()

        # Check if we should retry
        should_retry = (
            not terminal
            and self.attempt_number < self.MAX_ATTEMPTS
            and http_status not in (410, 404)  # Gone or Not Found = terminal
        )

        if should_retry:
            self.attempt_number += 1
            delay_index = min(self.attempt_number - 1, len(self.RETRY_DELAYS_SECONDS) - 1)
            delay_seconds = self.RETRY_DELAYS_SECONDS[delay_index]
            self.next_retry_at = timezone.now() + timezone.timedelta(seconds=delay_seconds)
            self.status = self.Status.PENDING
        else:
            self.status = self.Status.FAILURE
            self.next_retry_at = None

        self.save(
            update_fields=[
                "status",
                "error_type",
                "error_message",
                "http_status",
                "duration_ms",
                "response_snippet",
                "attempted_at",
                "attempt_number",
                "next_retry_at",
            ]
        )
        self.endpoint.record_delivery_failure()

    @classmethod
    def create_for_event(
        cls,
        endpoint: WebhookEndpoint,
        event_id: str,
        event_type: str,
    ) -> "WebhookDelivery":
        """
        Create a delivery record for an event.

        Returns existing record if already exists (idempotent).
        """
        delivery, _created = cls.objects.get_or_create(
            event_id=event_id,
            endpoint=endpoint,
            defaults={
                "event_type": event_type,
                "url_snapshot": endpoint.url,
            },
        )
        return delivery
