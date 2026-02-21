"""
Organizations models - multi-tenancy foundation.
"""

import re

from django.db import models
from django.utils import timezone

from apps.core.models import SoftDeleteAllManager, SoftDeleteManager, SoftDeleteMixin

# Maximum number of suffix attempts when resolving slug collisions.
MAX_SLUG_SUFFIX_ATTEMPTS = 100


class Organization(SoftDeleteMixin, models.Model):
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

    # Free trial
    trial_ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the free trial expires (null = no trial)",
    )
    trial_extended_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times the trial has been extended",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Managers - SoftDeleteManager excludes deleted by default
    objects = SoftDeleteManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_org_slug",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_trial_active(self) -> bool:
        if not self.trial_ends_at:
            return False
        return timezone.now() < self.trial_ends_at

    @property
    def trial_days_remaining(self) -> int:
        if not self.trial_ends_at:
            return 0
        remaining = (self.trial_ends_at - timezone.now()).days
        return max(0, remaining)


def generate_unique_slug(base_slug: str) -> str:
    """Return a slug that does not collide with any active organization.

    If *base_slug* is already free among active (non-deleted) orgs, it is
    returned unchanged.  Otherwise a numeric suffix is appended:
    ``base_slug-2``, ``base_slug-3``, etc.  If the base slug already ends
    with a numeric suffix (e.g. ``my-org-3``), the counter starts from the
    next number (``my-org-4``).

    Uses ``select_for_update()`` to lock colliding rows, preventing
    concurrent requests from generating the same slug (TOCTOU race).
    Must be called within a ``transaction.atomic()`` block.

    Raises ``RuntimeError`` after ``MAX_SLUG_SUFFIX_ATTEMPTS`` tries to
    prevent infinite loops.
    """
    if not Organization.objects.select_for_update().filter(slug=base_slug).exists():
        return base_slug

    # Strip an existing trailing numeric suffix so we increment from
    # the right starting point.  E.g. "my-org-3" -> ("my-org", 3).
    match = re.match(r"^(.+)-(\d+)$", base_slug)
    if match:
        stem = match.group(1)
        start = int(match.group(2)) + 1
    else:
        stem = base_slug
        start = 2

    for suffix in range(start, start + MAX_SLUG_SUFFIX_ATTEMPTS):
        candidate = f"{stem}-{suffix}"
        if not Organization.objects.select_for_update().filter(slug=candidate).exists():
            return candidate

    raise RuntimeError(
        f"Could not generate a unique slug after {MAX_SLUG_SUFFIX_ATTEMPTS} "
        f"attempts (base='{base_slug}')"
    )
