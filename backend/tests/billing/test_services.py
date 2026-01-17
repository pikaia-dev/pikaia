"""
Tests for billing services.

All Stripe API calls are mocked to isolate tests from external dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest

from apps.billing.models import Subscription
from apps.billing.services import (
    _get_tax_id_type,
    create_checkout_session,
    create_customer_portal_session,
    create_subscription_intent,
    get_or_create_stripe_customer,
    handle_subscription_created,
    handle_subscription_deleted,
    handle_subscription_updated,
    sync_billing_to_stripe,
    sync_subscription_from_stripe,
    sync_subscription_quantity,
)
from tests.accounts.factories import OrganizationFactory

from .factories import SubscriptionFactory


@pytest.mark.django_db
class TestGetOrCreateStripeCustomer:
    """Tests for get_or_create_stripe_customer service."""

    @patch("apps.billing.services.get_stripe")
    def test_creates_new_customer_when_none_exists(self, mock_get_stripe) -> None:
        """Should create Stripe customer when org has no customer ID."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_new_123")

        org = OrganizationFactory(stripe_customer_id="")

        customer_id = get_or_create_stripe_customer(org)

        assert customer_id == "cus_new_123"
        assert org.stripe_customer_id == "cus_new_123"
        mock_stripe.Customer.create.assert_called_once()

    @patch("apps.billing.services.get_stripe")
    def test_returns_existing_customer_id(self, mock_get_stripe) -> None:
        """Should return existing customer ID without creating new one."""
        org = OrganizationFactory(stripe_customer_id="cus_existing_456")

        customer_id = get_or_create_stripe_customer(org)

        assert customer_id == "cus_existing_456"
        mock_get_stripe.return_value.Customer.create.assert_not_called()

    @patch("apps.billing.services.get_stripe")
    def test_includes_billing_address_when_present(self, mock_get_stripe) -> None:
        """Should include billing address in customer creation."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_addr_123")

        org = OrganizationFactory(
            stripe_customer_id="",
            billing_address_line1="123 Main St",
            billing_city="New York",
            billing_country="US",
        )

        get_or_create_stripe_customer(org)

        call_kwargs = mock_stripe.Customer.create.call_args[1]
        assert "address" in call_kwargs
        assert call_kwargs["address"]["line1"] == "123 Main St"

    @patch("apps.billing.services.get_stripe")
    def test_adds_vat_id_for_eu_country(self, mock_get_stripe) -> None:
        """Should add VAT ID as tax_id for EU countries."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_eu_123")

        org = OrganizationFactory(
            stripe_customer_id="",
            billing_country="DE",
            vat_id="DE123456789",
        )

        get_or_create_stripe_customer(org)

        mock_stripe.Customer.create_tax_id.assert_called_once()
        assert mock_stripe.Customer.create_tax_id.call_args[1]["type"] == "eu_vat"


@pytest.mark.django_db
class TestSyncBillingToStripe:
    """Tests for sync_billing_to_stripe service."""

    @patch("apps.billing.services.get_stripe")
    def test_skips_when_no_customer_id(self, mock_get_stripe) -> None:
        """Should do nothing when org has no Stripe customer."""
        org = OrganizationFactory(stripe_customer_id="")

        sync_billing_to_stripe(org)

        mock_get_stripe.return_value.Customer.modify.assert_not_called()

    @patch("apps.billing.services.get_stripe")
    def test_updates_customer_with_billing_info(self, mock_get_stripe) -> None:
        """Should update Stripe customer with new billing info."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe

        org = OrganizationFactory(
            stripe_customer_id="cus_existing",
            billing_name="Acme Corp",
            billing_address_line1="456 Oak Ave",
        )

        sync_billing_to_stripe(org)

        mock_stripe.Customer.modify.assert_called()


@pytest.mark.django_db
class TestCreateCheckoutSession:
    """Tests for create_checkout_session service."""

    @patch("apps.billing.services.get_or_create_stripe_customer")
    @patch("apps.billing.services.get_stripe")
    def test_creates_session_with_correct_params(self, mock_get_stripe, mock_get_customer) -> None:
        """Should create checkout session with correct parameters."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_get_customer.return_value = "cus_test"
        mock_stripe.checkout.Session.create.return_value = MagicMock(
            url="https://checkout.stripe.com/test"
        )

        org = OrganizationFactory()

        url = create_checkout_session(
            org=org,
            quantity=5,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert url == "https://checkout.stripe.com/test"
        mock_stripe.checkout.Session.create.assert_called_once()


@pytest.mark.django_db
class TestCreateSubscriptionIntent:
    """Tests for create_subscription_intent service."""

    @patch("apps.billing.services.get_or_create_stripe_customer")
    @patch("apps.billing.services.get_stripe")
    def test_creates_subscription_with_incomplete_status(
        self, mock_get_stripe, mock_get_customer
    ) -> None:
        """Should create subscription with default_incomplete payment behavior."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_get_customer.return_value = "cus_test"

        # Mock nested response structure for Stripe 2025 API
        mock_subscription = MagicMock()
        mock_subscription.id = "sub_test_123"
        mock_subscription.latest_invoice.confirmation_secret.client_secret = "pi_secret_test"
        mock_stripe.Subscription.create.return_value = mock_subscription

        org = OrganizationFactory()

        client_secret, sub_id = create_subscription_intent(org=org, quantity=3)

        assert client_secret == "pi_secret_test"
        assert sub_id == "sub_test_123"

        call_kwargs = mock_stripe.Subscription.create.call_args[1]
        assert call_kwargs["payment_behavior"] == "default_incomplete"
        assert call_kwargs["items"][0]["quantity"] == 3


@pytest.mark.django_db
class TestSyncSubscriptionFromStripe:
    """Tests for sync_subscription_from_stripe service."""

    @patch("apps.billing.services.handle_subscription_created")
    @patch("apps.billing.services.get_stripe")
    def test_syncs_active_subscription(self, mock_get_stripe, mock_handle_created) -> None:
        """Should return True for active subscription."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_stripe.Subscription.retrieve.return_value = mock_sub

        result = sync_subscription_from_stripe("sub_test")

        assert result is True
        mock_handle_created.assert_called_once()

    @patch("apps.billing.services.handle_subscription_created")
    @patch("apps.billing.services.get_stripe")
    def test_returns_false_for_incomplete_subscription(
        self, mock_get_stripe, mock_handle_created
    ) -> None:
        """Should return False for incomplete subscription."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_sub = MagicMock()
        mock_sub.status = "incomplete"
        mock_stripe.Subscription.retrieve.return_value = mock_sub

        result = sync_subscription_from_stripe("sub_test")

        assert result is False


@pytest.mark.django_db
class TestSyncSubscriptionQuantity:
    """Tests for sync_subscription_quantity service."""

    @patch("apps.billing.services.get_stripe")
    def test_skips_when_no_subscription(self, mock_get_stripe) -> None:
        """Should do nothing when org has no subscription."""
        org = OrganizationFactory()

        sync_subscription_quantity(org)

        mock_get_stripe.return_value.Subscription.modify.assert_not_called()

    @patch("apps.billing.services.get_stripe")
    def test_skips_when_inactive_subscription(self, mock_get_stripe) -> None:
        """Should do nothing when subscription is not active."""
        sub = SubscriptionFactory(status=Subscription.Status.CANCELED)

        sync_subscription_quantity(sub.organization)

        mock_get_stripe.return_value.Subscription.modify.assert_not_called()

    @patch("apps.billing.services.get_stripe")
    def test_skips_when_quantity_matches(self, mock_get_stripe) -> None:
        """Should do nothing when member count matches subscription quantity."""
        from tests.accounts.factories import MemberFactory

        sub = SubscriptionFactory(quantity=2)
        MemberFactory(organization=sub.organization)
        MemberFactory(organization=sub.organization)

        sync_subscription_quantity(sub.organization)

        mock_get_stripe.return_value.Subscription.modify.assert_not_called()


@pytest.mark.django_db
class TestCreateCustomerPortalSession:
    """Tests for create_customer_portal_session service."""

    @patch("apps.billing.services.get_stripe")
    def test_creates_portal_session(self, mock_get_stripe) -> None:
        """Should create billing portal session."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.billing_portal.Session.create.return_value = MagicMock(
            url="https://billing.stripe.com/portal"
        )

        org = OrganizationFactory(stripe_customer_id="cus_test")

        url = create_customer_portal_session(org=org, return_url="https://example.com/billing")

        assert url == "https://billing.stripe.com/portal"

    def test_raises_when_no_customer(self) -> None:
        """Should raise ValueError when org has no Stripe customer."""
        org = OrganizationFactory(stripe_customer_id="")

        with pytest.raises(ValueError, match="no Stripe customer"):
            create_customer_portal_session(org=org, return_url="https://example.com")


@pytest.mark.django_db
class TestHandleSubscriptionCreated:
    """Tests for handle_subscription_created webhook handler."""

    def test_creates_subscription_from_stripe_data(self) -> None:
        """Should create local subscription from Stripe webhook data."""
        org = OrganizationFactory()

        stripe_data = {
            "id": "sub_webhook_123",
            "status": "active",
            "current_period": {
                "start": 1704067200,  # 2024-01-01
                "end": 1706745600,  # 2024-02-01
            },
            "items": {"data": [{"price": {"id": "price_test"}, "quantity": 5}]},
            "cancel_at_period_end": False,
            "metadata": {"organization_id": str(org.id)},
        }

        handle_subscription_created(stripe_data)

        sub = Subscription.objects.get(stripe_subscription_id="sub_webhook_123")
        assert sub.organization == org
        assert sub.status == "active"
        assert sub.quantity == 5

    def test_handles_legacy_period_format(self) -> None:
        """Should handle old Stripe API format with flat period fields."""
        org = OrganizationFactory()

        stripe_data = {
            "id": "sub_legacy_123",
            "status": "active",
            "current_period_start": 1704067200,
            "current_period_end": 1706745600,
            "items": {"data": [{"price": {"id": "price_test"}, "quantity": 1}]},
            "cancel_at_period_end": False,
            "metadata": {"organization_id": str(org.id)},
        }

        handle_subscription_created(stripe_data)

        sub = Subscription.objects.get(stripe_subscription_id="sub_legacy_123")
        assert sub.organization == org

    def test_ignores_missing_org_id_in_metadata(self) -> None:
        """Should log warning and return when no org ID in metadata."""
        stripe_data = {
            "id": "sub_no_org",
            "status": "active",
            "current_period": {"start": 1704067200, "end": 1706745600},
            "items": {"data": []},
            "metadata": {},
        }

        # Should not raise
        handle_subscription_created(stripe_data)

        assert not Subscription.objects.filter(stripe_subscription_id="sub_no_org").exists()

    def test_updates_existing_subscription(self) -> None:
        """Should update subscription if it already exists."""
        sub = SubscriptionFactory(
            stripe_subscription_id="sub_existing",
            status=Subscription.Status.INCOMPLETE,
            quantity=1,
        )

        stripe_data = {
            "id": "sub_existing",
            "status": "active",
            "current_period": {"start": 1704067200, "end": 1706745600},
            "items": {"data": [{"price": {"id": "price_new"}, "quantity": 10}]},
            "cancel_at_period_end": True,
            "metadata": {"organization_id": str(sub.organization.id)},
        }

        handle_subscription_created(stripe_data)

        sub.refresh_from_db()
        assert sub.status == "active"
        assert sub.quantity == 10
        assert sub.cancel_at_period_end is True


@pytest.mark.django_db
class TestHandleSubscriptionUpdated:
    """Tests for handle_subscription_updated webhook handler."""

    def test_updates_existing_subscription(self) -> None:
        """Should update an existing subscription."""
        sub = SubscriptionFactory(
            stripe_subscription_id="sub_update_test",
            status=Subscription.Status.ACTIVE,
            quantity=1,
        )

        stripe_data = {
            "id": "sub_update_test",
            "status": "past_due",
            "current_period": {"start": 1704067200, "end": 1706745600},
            "items": {"data": [{"price": {"id": "price_test"}, "quantity": 3}]},
            "cancel_at_period_end": True,
        }

        handle_subscription_updated(stripe_data)

        sub.refresh_from_db()
        assert sub.status == "past_due"
        assert sub.quantity == 3
        assert sub.cancel_at_period_end is True

    def test_creates_subscription_if_not_exists(self) -> None:
        """Should create subscription via handle_subscription_created if not found."""
        org = OrganizationFactory()

        stripe_data = {
            "id": "sub_new_from_update",
            "status": "active",
            "current_period": {"start": 1704067200, "end": 1706745600},
            "items": {"data": [{"price": {"id": "price_test"}, "quantity": 1}]},
            "cancel_at_period_end": False,
            "metadata": {"organization_id": str(org.id)},
        }

        handle_subscription_updated(stripe_data)

        assert Subscription.objects.filter(stripe_subscription_id="sub_new_from_update").exists()


@pytest.mark.django_db
class TestHandleSubscriptionDeleted:
    """Tests for handle_subscription_deleted webhook handler."""

    def test_marks_subscription_as_canceled(self) -> None:
        """Should set subscription status to canceled."""
        sub = SubscriptionFactory(
            stripe_subscription_id="sub_delete_test",
            status=Subscription.Status.ACTIVE,
        )

        stripe_data = {"id": "sub_delete_test"}

        handle_subscription_deleted(stripe_data)

        sub.refresh_from_db()
        assert sub.status == Subscription.Status.CANCELED

    def test_handles_non_existent_subscription(self) -> None:
        """Should not raise when subscription doesn't exist."""
        stripe_data = {"id": "sub_nonexistent"}

        # Should not raise
        handle_subscription_deleted(stripe_data)


class TestGetTaxIdType:
    """Tests for _get_tax_id_type helper function."""

    def test_returns_eu_vat_for_eu_countries(self) -> None:
        """Should return eu_vat for EU member states."""
        eu_countries = ["DE", "FR", "IT", "ES", "PL", "NL", "BE", "SE"]
        for country in eu_countries:
            assert _get_tax_id_type(country, "VAT123") == "eu_vat"

    def test_returns_gb_vat_for_uk(self) -> None:
        """Should return gb_vat for United Kingdom."""
        assert _get_tax_id_type("GB", "VAT123") == "gb_vat"

    def test_returns_ch_vat_for_switzerland(self) -> None:
        """Should return ch_vat for Switzerland."""
        assert _get_tax_id_type("CH", "VAT123") == "ch_vat"

    def test_returns_us_ein_for_us(self) -> None:
        """Should return us_ein for United States."""
        assert _get_tax_id_type("US", "123456789") == "us_ein"

    def test_returns_none_for_unsupported_country(self) -> None:
        """Should return None for unsupported countries."""
        assert _get_tax_id_type("XX", "123") is None
