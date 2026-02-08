"""
Tests for organizations app models and business logic.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.organizations.models import Organization
from tests.accounts.factories import OrganizationFactory


@pytest.mark.django_db
class TestOrganizationModel:
    """Tests for Organization model."""

    def test_create_organization(self) -> None:
        """Should create an organization with required fields."""
        org = Organization.objects.create(
            stytch_org_id="org-test-123",
            name="Test Org",
            slug="test-org",
        )

        assert org.id is not None
        assert org.stytch_org_id == "org-test-123"
        assert org.name == "Test Org"
        assert org.slug == "test-org"

    def test_str_returns_name(self) -> None:
        """Should return organization name as string representation."""
        org = OrganizationFactory.create(name="Acme Corp")

        assert str(org) == "Acme Corp"

    def test_stytch_org_id_unique(self) -> None:
        """Should enforce unique stytch_org_id."""
        OrganizationFactory.create(stytch_org_id="org-unique-123")

        with pytest.raises(IntegrityError):
            OrganizationFactory.create(stytch_org_id="org-unique-123")

    def test_slug_unique(self) -> None:
        """Should enforce unique slug."""
        OrganizationFactory.create(slug="unique-slug")

        with pytest.raises(IntegrityError):
            OrganizationFactory.create(slug="unique-slug")

    def test_timestamps_auto_set(self) -> None:
        """Should auto-set created_at and updated_at."""
        org = OrganizationFactory.create()

        assert org.created_at is not None
        assert org.updated_at is not None

    def test_ordering_by_created_at_desc(self) -> None:
        """Should order organizations by created_at descending."""
        org1 = OrganizationFactory.create()
        org2 = OrganizationFactory.create()
        org3 = OrganizationFactory.create()

        orgs = list(Organization.objects.all())

        # Should be newest first
        assert orgs[0] == org3
        assert orgs[1] == org2
        assert orgs[2] == org1


@pytest.mark.django_db
class TestOrganizationBillingFields:
    """Tests for Organization billing-related fields."""

    def test_billing_email_optional(self) -> None:
        """Should allow blank billing_email."""
        org = OrganizationFactory.create(billing_email="")

        assert org.billing_email == ""

    def test_use_billing_email_default_false(self) -> None:
        """Should default use_billing_email to False."""
        org = OrganizationFactory.create()

        assert org.use_billing_email is False

    def test_billing_address_fields_optional(self) -> None:
        """Should allow all billing address fields to be blank."""
        org = OrganizationFactory.create(
            billing_name="",
            billing_address_line1="",
            billing_address_line2="",
            billing_city="",
            billing_state="",
            billing_postal_code="",
            billing_country="",
        )

        assert org.billing_name == ""
        assert org.billing_address_line1 == ""
        assert org.billing_country == ""

    def test_vat_id_optional(self) -> None:
        """Should allow blank vat_id."""
        org = OrganizationFactory.create(vat_id="")

        assert org.vat_id == ""

    def test_stripe_customer_id_optional(self) -> None:
        """Should allow blank stripe_customer_id."""
        org = OrganizationFactory.create(stripe_customer_id="")

        assert org.stripe_customer_id == ""

    def test_stripe_customer_id_stored(self) -> None:
        """Should store Stripe customer ID."""
        org = OrganizationFactory.create(stripe_customer_id="cus_test123")

        org.refresh_from_db()
        assert org.stripe_customer_id == "cus_test123"


@pytest.mark.django_db
class TestOrganizationLogo:
    """Tests for Organization logo field."""

    def test_logo_url_optional(self) -> None:
        """Should allow blank logo_url."""
        org = OrganizationFactory.create(logo_url="")

        assert org.logo_url == ""

    def test_logo_url_stored(self) -> None:
        """Should store valid URL."""
        org = OrganizationFactory.create(logo_url="https://example.com/logo.png")

        org.refresh_from_db()
        assert org.logo_url == "https://example.com/logo.png"


@pytest.mark.django_db
class TestOrganizationQueryset:
    """Tests for Organization queryset operations."""

    def test_filter_by_stytch_org_id(self) -> None:
        """Should be able to filter by stytch_org_id."""
        org = OrganizationFactory.create(stytch_org_id="org-filter-test")
        OrganizationFactory.create()  # Another org

        result = Organization.objects.filter(stytch_org_id="org-filter-test").first()

        assert result == org

    def test_filter_by_slug(self) -> None:
        """Should be able to filter by slug."""
        org = OrganizationFactory.create(slug="searchable-slug")
        OrganizationFactory.create()  # Another org

        result = Organization.objects.filter(slug="searchable-slug").first()

        assert result == org

    def test_filter_by_stripe_customer_id(self) -> None:
        """Should be able to filter by stripe_customer_id for billing lookups."""
        org = OrganizationFactory.create(stripe_customer_id="cus_lookup123")
        OrganizationFactory.create()  # Another org

        result = Organization.objects.filter(stripe_customer_id="cus_lookup123").first()

        assert result == org


@pytest.mark.django_db
class TestOrganizationTrial:
    """Tests for Organization trial fields and properties."""

    def test_is_trial_active_when_future(self) -> None:
        """Should return True when trial_ends_at is in the future."""
        org = OrganizationFactory.create(trial_ends_at=timezone.now() + timedelta(days=7))

        assert org.is_trial_active is True

    def test_is_trial_active_when_past(self) -> None:
        """Should return False when trial_ends_at is in the past."""
        org = OrganizationFactory.create(trial_ends_at=timezone.now() - timedelta(days=1))

        assert org.is_trial_active is False

    def test_is_trial_active_when_null(self) -> None:
        """Should return False when trial_ends_at is None."""
        org = OrganizationFactory.create(trial_ends_at=None)

        assert org.is_trial_active is False

    def test_trial_days_remaining_future(self) -> None:
        """Should return positive days when trial is active."""
        org = OrganizationFactory.create(trial_ends_at=timezone.now() + timedelta(days=10))

        assert org.trial_days_remaining >= 9  # Account for test execution time

    def test_trial_days_remaining_past(self) -> None:
        """Should return 0 when trial has expired."""
        org = OrganizationFactory.create(trial_ends_at=timezone.now() - timedelta(days=3))

        assert org.trial_days_remaining == 0

    def test_trial_days_remaining_null(self) -> None:
        """Should return 0 when trial_ends_at is None."""
        org = OrganizationFactory.create(trial_ends_at=None)

        assert org.trial_days_remaining == 0

    def test_trial_extended_count_default(self) -> None:
        """Should default trial_extended_count to 0."""
        org = OrganizationFactory.create()

        assert org.trial_extended_count == 0
