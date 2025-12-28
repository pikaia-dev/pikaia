"""
Organizations models - multi-tenancy foundation.
"""

from django.db import models


class Organization(models.Model):
    """
    Local replica of Stytch Organization.

    Stytch is the source of truth for org/member data.
    This model syncs via webhooks and holds app-specific extensions.
    """

    # Stytch sync
    stytch_org_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stytch organization_id, e.g. 'organization-xxx'",
    )

    # Organization info
    name = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-safe identifier, e.g. 'acme-corp'",
    )

    # Stripe integration (populated when org upgrades to paid)
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Stripe customer ID, e.g. 'cus_xxx'",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
