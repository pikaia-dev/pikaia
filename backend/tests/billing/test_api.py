"""
Tests for billing API endpoints.

Covers all billing endpoints with mocked Stripe services.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory
from ninja.errors import HttpError

from apps.billing.api import (
    confirm_subscription_endpoint,
    create_checkout,
    create_portal,
    create_subscription_intent_endpoint,
    get_subscription,
)
from apps.billing.models import Subscription
from apps.billing.schemas import (
    CheckoutSessionRequest,
    ConfirmSubscriptionRequest,
    PortalSessionRequest,
    SubscriptionIntentRequest,
)
from apps.core.auth import AuthContext
from tests.accounts.factories import MemberFactory, OrganizationFactory
from tests.conftest import create_authenticated_request

from .factories import SubscriptionFactory


@pytest.mark.django_db
class TestGetSubscription:
    """Tests for get_subscription endpoint."""

    def test_returns_active_subscription(self, request_factory: RequestFactory) -> None:
        """Should return subscription details when org has active subscription."""
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE, quantity=5)
        org = sub.organization

        request = create_authenticated_request(
            request_factory, "get", "/api/v1/billing/subscription", org=org
        )

        result = get_subscription(request)

        assert result.status == "active"
        assert result.quantity == 5
        assert result.current_period_end is not None

    def test_returns_none_status_when_no_subscription(
        self, request_factory: RequestFactory
    ) -> None:
        """Should return 'none' status when org has no subscription."""
        org = OrganizationFactory()
        MemberFactory(organization=org)  # Add at least one member

        request = create_authenticated_request(
            request_factory, "get", "/api/v1/billing/subscription", org=org
        )

        result = get_subscription(request)

        assert result.status == "none"
        assert result.quantity >= 1  # Should default to member count

    def test_unauthenticated_returns_401(self, request_factory: RequestFactory) -> None:
        """Should raise 401 when not authenticated."""
        request = request_factory.get("/api/v1/billing/subscription")

        with pytest.raises(HttpError) as exc_info:
            get_subscription(request)

        assert exc_info.value.status_code == 401


@pytest.mark.django_db
class TestCreateCheckout:
    """Tests for create_checkout endpoint."""

    @patch("apps.billing.api.create_checkout_session")
    def test_admin_can_create_checkout(
        self, mock_create_session, request_factory: RequestFactory
    ) -> None:
        """Admin should be able to create checkout session."""
        mock_create_session.return_value = "https://checkout.stripe.com/test"
        org = OrganizationFactory()

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/checkout", org=org, role="admin"
        )
        payload = CheckoutSessionRequest(
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            quantity=3,
        )

        result = create_checkout(request, payload)

        assert result.checkout_url == "https://checkout.stripe.com/test"
        mock_create_session.assert_called_once()

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/checkout", org=org, role="member"
        )
        payload = CheckoutSessionRequest(
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        with pytest.raises(HttpError) as exc_info:
            create_checkout(request, payload)

        assert exc_info.value.status_code == 403

    def test_already_subscribed_returns_400(self, request_factory: RequestFactory) -> None:
        """Should return 400 if org already has active subscription."""
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE)
        org = sub.organization

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/checkout", org=org, role="admin"
        )
        payload = CheckoutSessionRequest(
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        with pytest.raises(HttpError) as exc_info:
            create_checkout(request, payload)

        assert exc_info.value.status_code == 400
        assert "Already subscribed" in str(exc_info.value.message)


@pytest.mark.django_db
class TestCreatePortal:
    """Tests for create_portal endpoint."""

    @patch("apps.billing.api.create_customer_portal_session")
    def test_admin_can_create_portal(
        self, mock_create_portal, request_factory: RequestFactory
    ) -> None:
        """Admin should be able to create billing portal session."""
        mock_create_portal.return_value = "https://billing.stripe.com/portal"
        org = OrganizationFactory(stripe_customer_id="cus_test")

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/portal", org=org, role="admin"
        )
        payload = PortalSessionRequest(return_url="https://example.com/billing")

        result = create_portal(request, payload)

        assert result.portal_url == "https://billing.stripe.com/portal"

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory(stripe_customer_id="cus_test")

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/portal", org=org, role="member"
        )
        payload = PortalSessionRequest(return_url="https://example.com/billing")

        with pytest.raises(HttpError) as exc_info:
            create_portal(request, payload)

        assert exc_info.value.status_code == 403

    def test_no_customer_returns_400(self, request_factory: RequestFactory) -> None:
        """Should return 400 if org has no Stripe customer."""
        org = OrganizationFactory(stripe_customer_id="")

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/portal", org=org, role="admin"
        )
        payload = PortalSessionRequest(return_url="https://example.com/billing")

        with pytest.raises(HttpError) as exc_info:
            create_portal(request, payload)

        assert exc_info.value.status_code == 400


@pytest.mark.django_db
class TestCreateSubscriptionIntent:
    """Tests for create_subscription_intent endpoint."""

    @patch("apps.billing.api.create_subscription_intent")
    def test_admin_can_create_intent(
        self, mock_create_intent, request_factory: RequestFactory
    ) -> None:
        """Admin should be able to create subscription intent."""
        mock_create_intent.return_value = ("pi_secret_test", "sub_test_123")
        org = OrganizationFactory()

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/subscription-intent", org=org, role="admin"
        )
        payload = SubscriptionIntentRequest(quantity=5)

        result = create_subscription_intent_endpoint(request, payload)

        assert result.client_secret == "pi_secret_test"
        assert result.subscription_id == "sub_test_123"

    @patch("apps.billing.api.create_subscription_intent")
    def test_uses_member_count_when_no_quantity(
        self, mock_create_intent, request_factory: RequestFactory
    ) -> None:
        """Should use org member count when quantity not specified."""
        mock_create_intent.return_value = ("pi_secret", "sub_123")
        org = OrganizationFactory()
        # Create 3 members
        MemberFactory(organization=org)
        MemberFactory(organization=org)
        MemberFactory(organization=org)

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/subscription-intent", org=org, role="admin"
        )
        payload = SubscriptionIntentRequest(quantity=None)

        create_subscription_intent_endpoint(request, payload)

        # Should be called with quantity=3 (member count)
        call_kwargs = mock_create_intent.call_args[1]
        assert call_kwargs["quantity"] >= 1

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/subscription-intent", org=org, role="member"
        )
        payload = SubscriptionIntentRequest()

        with pytest.raises(HttpError) as exc_info:
            create_subscription_intent_endpoint(request, payload)

        assert exc_info.value.status_code == 403

    def test_already_subscribed_returns_400(self, request_factory: RequestFactory) -> None:
        """Should return 400 if org already has active subscription."""
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE)
        org = sub.organization

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/subscription-intent", org=org, role="admin"
        )
        payload = SubscriptionIntentRequest()

        with pytest.raises(HttpError) as exc_info:
            create_subscription_intent_endpoint(request, payload)

        assert exc_info.value.status_code == 400


@pytest.mark.django_db
class TestConfirmSubscription:
    """Tests for confirm_subscription endpoint."""

    @patch("apps.billing.api.sync_subscription_from_stripe")
    def test_admin_can_confirm_subscription(
        self, mock_sync, request_factory: RequestFactory
    ) -> None:
        """Admin should be able to confirm subscription."""
        mock_sync.return_value = True
        org = OrganizationFactory()

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/confirm-subscription", org=org, role="admin"
        )
        payload = ConfirmSubscriptionRequest(subscription_id="sub_test_123")

        result = confirm_subscription_endpoint(request, payload)

        assert result.is_active is True
        mock_sync.assert_called_once_with("sub_test_123")

    @patch("apps.billing.api.sync_subscription_from_stripe")
    def test_returns_false_when_not_active(
        self, mock_sync, request_factory: RequestFactory
    ) -> None:
        """Should return is_active=False when subscription is not yet active."""
        mock_sync.return_value = False
        org = OrganizationFactory()

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/confirm-subscription", org=org, role="admin"
        )
        payload = ConfirmSubscriptionRequest(subscription_id="sub_incomplete")

        result = confirm_subscription_endpoint(request, payload)

        assert result.is_active is False

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/confirm-subscription", org=org, role="member"
        )
        payload = ConfirmSubscriptionRequest(subscription_id="sub_test")

        with pytest.raises(HttpError) as exc_info:
            confirm_subscription_endpoint(request, payload)

        assert exc_info.value.status_code == 403

    @patch("apps.billing.api.sync_subscription_from_stripe")
    def test_stripe_error_returns_500(self, mock_sync, request_factory: RequestFactory) -> None:
        """Should return 500 on Stripe errors."""
        mock_sync.side_effect = Exception("Stripe API error")
        org = OrganizationFactory()

        request = create_authenticated_request(
            request_factory, "post", "/api/v1/billing/confirm-subscription", org=org, role="admin"
        )
        payload = ConfirmSubscriptionRequest(subscription_id="sub_test")

        with pytest.raises(HttpError) as exc_info:
            confirm_subscription_endpoint(request, payload)

        assert exc_info.value.status_code == 500


@pytest.mark.django_db
class TestListInvoices:
    """Tests for list_invoices endpoint."""

    @patch("apps.billing.api.get_stripe")
    def test_admin_can_list_invoices(
        self, mock_get_stripe, request_factory: RequestFactory
    ) -> None:
        """Admin should be able to list invoices."""
        from apps.billing.api import list_invoices

        # Mock Stripe response
        mock_stripe = MagicMock()
        mock_invoice = MagicMock()
        mock_invoice.id = "in_test_123"
        mock_invoice.number = "INV-0001"
        mock_invoice.status = "paid"
        mock_invoice.amount_due = 1000
        mock_invoice.amount_paid = 1000
        mock_invoice.currency = "usd"
        mock_invoice.created = 1704067200  # 2024-01-01 00:00:00 UTC
        mock_invoice.hosted_invoice_url = "https://invoice.stripe.com/test"
        mock_invoice.invoice_pdf = "https://invoice.stripe.com/test.pdf"
        mock_invoice.period_start = 1704067200
        mock_invoice.period_end = 1706745600

        mock_invoice_list = MagicMock()
        mock_invoice_list.data = [mock_invoice]
        mock_invoice_list.has_more = False
        mock_stripe.Invoice.list.return_value = mock_invoice_list
        mock_get_stripe.return_value = mock_stripe

        org = OrganizationFactory(stripe_customer_id="cus_test")

        request = create_authenticated_request(
            request_factory, "get", "/api/v1/billing/invoices", org=org, role="admin"
        )

        result = list_invoices(request)

        assert len(result.invoices) == 1
        assert result.invoices[0].id == "in_test_123"
        assert result.invoices[0].number == "INV-0001"
        assert result.invoices[0].status == "paid"
        assert result.invoices[0].amount_paid == 1000
        assert result.has_more is False

    def test_returns_empty_when_no_customer(self, request_factory: RequestFactory) -> None:
        """Should return empty list when org has no Stripe customer."""
        from apps.billing.api import list_invoices

        org = OrganizationFactory(stripe_customer_id="")

        request = create_authenticated_request(
            request_factory, "get", "/api/v1/billing/invoices", org=org, role="admin"
        )

        result = list_invoices(request)

        assert result.invoices == []
        assert result.has_more is False

    @patch("apps.billing.api.get_stripe")
    def test_pagination_params_passed_to_stripe(
        self, mock_get_stripe, request_factory: RequestFactory
    ) -> None:
        """Should pass pagination params to Stripe API."""
        from apps.billing.api import list_invoices

        mock_stripe = MagicMock()
        mock_invoice_list = MagicMock()
        mock_invoice_list.data = []
        mock_invoice_list.has_more = False
        mock_stripe.Invoice.list.return_value = mock_invoice_list
        mock_get_stripe.return_value = mock_stripe

        org = OrganizationFactory(stripe_customer_id="cus_test")

        request = create_authenticated_request(
            request_factory, "get", "/api/v1/billing/invoices", org=org, role="admin"
        )

        list_invoices(request, limit=5, starting_after="in_prev")

        mock_stripe.Invoice.list.assert_called_once_with(
            customer="cus_test",
            limit=5,
            starting_after="in_prev",
        )

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        from apps.billing.api import list_invoices

        org = OrganizationFactory(stripe_customer_id="cus_test")

        request = create_authenticated_request(
            request_factory, "get", "/api/v1/billing/invoices", org=org, role="member"
        )

        with pytest.raises(HttpError) as exc_info:
            list_invoices(request)

        assert exc_info.value.status_code == 403

    @patch("apps.billing.api.get_stripe")
    def test_stripe_error_returns_500(
        self, mock_get_stripe, request_factory: RequestFactory
    ) -> None:
        """Should return 500 on Stripe errors."""
        from apps.billing.api import list_invoices

        mock_stripe = MagicMock()
        mock_stripe.Invoice.list.side_effect = Exception("Stripe API error")
        mock_get_stripe.return_value = mock_stripe

        org = OrganizationFactory(stripe_customer_id="cus_test")

        request = create_authenticated_request(
            request_factory, "get", "/api/v1/billing/invoices", org=org, role="admin"
        )

        with pytest.raises(HttpError) as exc_info:
            list_invoices(request)

        assert exc_info.value.status_code == 500
