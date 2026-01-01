"""
Tests for organizations app models and business logic.
"""

import pytest
from django.db import IntegrityError

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
        org = OrganizationFactory(name="Acme Corp")

        assert str(org) == "Acme Corp"

    def test_stytch_org_id_unique(self) -> None:
        """Should enforce unique stytch_org_id."""
        OrganizationFactory(stytch_org_id="org-unique-123")

        with pytest.raises(IntegrityError):
            OrganizationFactory(stytch_org_id="org-unique-123")

    def test_slug_unique(self) -> None:
        """Should enforce unique slug."""
        OrganizationFactory(slug="unique-slug")

        with pytest.raises(IntegrityError):
            OrganizationFactory(slug="unique-slug")

    def test_timestamps_auto_set(self) -> None:
        """Should auto-set created_at and updated_at."""
        org = OrganizationFactory()

        assert org.created_at is not None
        assert org.updated_at is not None

    def test_ordering_by_created_at_desc(self) -> None:
        """Should order organizations by created_at descending."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        org3 = OrganizationFactory()

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
        org = OrganizationFactory(billing_email="")

        assert org.billing_email == ""

    def test_use_billing_email_default_false(self) -> None:
        """Should default use_billing_email to False."""
        org = OrganizationFactory()

        assert org.use_billing_email is False

    def test_billing_address_fields_optional(self) -> None:
        """Should allow all billing address fields to be blank."""
        org = OrganizationFactory(
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
        org = OrganizationFactory(vat_id="")

        assert org.vat_id == ""

    def test_stripe_customer_id_optional(self) -> None:
        """Should allow blank stripe_customer_id."""
        org = OrganizationFactory(stripe_customer_id="")

        assert org.stripe_customer_id == ""

    def test_stripe_customer_id_stored(self) -> None:
        """Should store Stripe customer ID."""
        org = OrganizationFactory(stripe_customer_id="cus_test123")

        org.refresh_from_db()
        assert org.stripe_customer_id == "cus_test123"


@pytest.mark.django_db
class TestOrganizationLogo:
    """Tests for Organization logo field."""

    def test_logo_url_optional(self) -> None:
        """Should allow blank logo_url."""
        org = OrganizationFactory(logo_url="")

        assert org.logo_url == ""

    def test_logo_url_stored(self) -> None:
        """Should store valid URL."""
        org = OrganizationFactory(logo_url="https://example.com/logo.png")

        org.refresh_from_db()
        assert org.logo_url == "https://example.com/logo.png"


@pytest.mark.django_db
class TestOrganizationQueryset:
    """Tests for Organization queryset operations."""

    def test_filter_by_stytch_org_id(self) -> None:
        """Should be able to filter by stytch_org_id."""
        org = OrganizationFactory(stytch_org_id="org-filter-test")
        OrganizationFactory()  # Another org

        result = Organization.objects.filter(stytch_org_id="org-filter-test").first()

        assert result == org

    def test_filter_by_slug(self) -> None:
        """Should be able to filter by slug."""
        org = OrganizationFactory(slug="searchable-slug")
        OrganizationFactory()  # Another org

        result = Organization.objects.filter(slug="searchable-slug").first()

        assert result == org

    def test_filter_by_stripe_customer_id(self) -> None:
        """Should be able to filter by stripe_customer_id for billing lookups."""
        org = OrganizationFactory(stripe_customer_id="cus_lookup123")
        OrganizationFactory()  # Another org

        result = Organization.objects.filter(stripe_customer_id="cus_lookup123").first()

        assert result == org
