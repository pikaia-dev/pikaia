"""
Organizations models - multi-tenancy foundation.
"""

from django.db import models


class OrganizationManager(models.Manager):
    """Custom manager for Organization model that excludes soft-deleted orgs."""

    def get_queryset(self) -> models.QuerySet:
        """Return only active (non-deleted) organizations by default."""
        return super().get_queryset().filter(deleted_at__isnull=True)


class OrganizationAllManager(models.Manager):
    """Manager that includes all organizations, including soft-deleted ones."""

    pass


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

    # Soft delete
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Soft delete timestamp. NULL = active organization.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Managers
    objects = OrganizationManager()
    all_objects = OrganizationAllManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_deleted(self) -> bool:
        """Check if organization is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this organization by setting deleted_at timestamp."""
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])
