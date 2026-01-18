"""
Billing models - Stripe subscriptions and payment tracking.
"""

from django.db import models

from apps.organizations.models import Organization


class Subscription(models.Model):
    """
    Stripe subscription for an organization.

    Tracks subscription status and seat count.
    Source of truth is Stripe - synced via webhooks.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELED = "canceled", "Canceled"
        INCOMPLETE = "incomplete", "Incomplete"
        INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete Expired"
        TRIALING = "trialing", "Trialing"
        UNPAID = "unpaid", "Unpaid"
        PAUSED = "paused", "Paused"

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stripe subscription ID, e.g. 'sub_xxx'",
    )
    stripe_price_id = models.CharField(
        max_length=255,
        help_text="Stripe price ID, e.g. 'price_xxx'",
    )
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.INCOMPLETE,
        db_index=True,
        help_text="Subscription status from Stripe",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Number of seats (synced with member count)",
    )
    current_period_start = models.DateTimeField(
        help_text="Start of current billing period",
    )
    current_period_end = models.DateTimeField(
        help_text="End of current billing period (next invoice date)",
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="If True, subscription will cancel at period end",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.status}"

    @property
    def is_active(self) -> bool:
        """Check if subscription is in a usable state."""
        return self.status in (self.Status.ACTIVE, self.Status.TRIALING)
