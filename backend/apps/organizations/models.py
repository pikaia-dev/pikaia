"""
Organizations models - multi-tenancy foundation.
"""

from django.db import models


class Organization(models.Model):
    """
    Local replica of Stytch Organization.

    Stytch is the source of truth for org/member data.
    This model syncs via webhooks and holds app-specific extensions.
    Billing data is owned by our system and synced OUT to Stripe.
    """

    # Stytch sync
    stytch_org_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stytch organization_id, e.g. 'organization-xxx'",
    )

    # Organization info (synced to Stytch)
    name = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-safe identifier, e.g. 'acme-corp'",
    )
    logo_url = models.URLField(
        blank=True,
        default="",
        help_text="URL to organization's logo image",
    )

    # Stripe integration (populated when org upgrades to paid)
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Stripe customer ID, e.g. 'cus_xxx'",
    )

    # Billing info - owned by our system, synced to Stripe
    use_billing_email = models.BooleanField(
        default=False,
        help_text="If True, send invoices to billing_email; otherwise send to admin",
    )
    billing_email = models.EmailField(
        blank=True,
        help_text="Email for invoices (used only if use_billing_email is True)",
    )
    billing_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Legal/company name for invoices",
    )
    billing_address_line1 = models.CharField(max_length=255, blank=True)
    billing_address_line2 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=20, blank=True)
    billing_country = models.CharField(
        max_length=2,
        blank=True,
        help_text="ISO 3166-1 alpha-2 country code",
    )
    vat_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="EU VAT number, e.g. 'DE123456789'",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

