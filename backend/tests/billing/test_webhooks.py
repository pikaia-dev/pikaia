"""
Tests for Stripe webhook handler.

Tests signature verification, event dispatching, and error handling.
"""

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import stripe

if TYPE_CHECKING:
    from django.test import Client


@pytest.fixture
def webhook_url() -> str:
    """Webhook endpoint URL (module-specific)."""
    return "/webhooks/stripe/"


def build_webhook_payload(
    event_type: str, data_object: dict, event_id: str = "evt_test_123"
) -> dict:
    """Build a Stripe webhook event payload."""
    return {
        "id": event_id,
        "type": event_type,
        "data": {"object": data_object},
    }


class TestStripeWebhookSignatureVerification:
    """Tests for webhook signature verification."""

    def test_missing_signature_header_returns_400(self, client: Client, webhook_url: str) -> None:
        """Should return 400 when Stripe-Signature header is missing."""
        response = client.post(
            webhook_url,
            data=json.dumps({"type": "test"}),
            content_type="application/json",
        )

        assert response.status_code == 400

    @patch("apps.billing.webhooks.settings")
    def test_missing_webhook_secret_returns_500(
        self, mock_settings: MagicMock, client: Client, webhook_url: str
    ) -> None:
        """Should return 500 when STRIPE_WEBHOOK_SECRET is not configured."""
        mock_settings.STRIPE_WEBHOOK_SECRET = ""

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "test"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        assert response.status_code == 500

    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_invalid_payload_returns_400(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should return 400 when payload is invalid."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_construct.side_effect = ValueError("Invalid payload")

        response = client.post(
            webhook_url,
            data="invalid json",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature",
        )

        assert response.status_code == 400

    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_invalid_signature_returns_400(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should return 400 when signature verification fails."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_construct.side_effect = stripe.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "test"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid_signature",
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestStripeWebhookEventDispatching:
    """Tests for webhook event dispatching to handlers."""

    @patch("apps.billing.webhooks.handle_subscription_created")
    @patch("apps.billing.webhooks.stripe.Subscription.retrieve")
    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_checkout_session_completed_with_subscription(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        mock_retrieve: MagicMock,
        mock_handler: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should fetch subscription and call handler for checkout.session.completed."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        subscription_data = {"id": "sub_123", "status": "active"}
        mock_retrieve.return_value = subscription_data
        mock_construct.return_value = build_webhook_payload(
            "checkout.session.completed",
            {"subscription": "sub_123"},
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "checkout.session.completed"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200
        mock_retrieve.assert_called_once_with("sub_123")
        mock_handler.assert_called_once_with(subscription_data)

    @patch("apps.billing.webhooks.handle_subscription_created")
    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_subscription_created_event(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        mock_handler: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should call handle_subscription_created for customer.subscription.created."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        subscription_data = {"id": "sub_123", "status": "active"}
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.created",
            subscription_data,
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.created"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200
        mock_handler.assert_called_once_with(subscription_data)

    @patch("apps.billing.webhooks.handle_subscription_updated")
    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_subscription_updated_event(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        mock_handler: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should call handle_subscription_updated for customer.subscription.updated."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        subscription_data = {"id": "sub_123", "status": "active"}
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.updated",
            subscription_data,
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.updated"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200
        mock_handler.assert_called_once_with(subscription_data)

    @patch("apps.billing.webhooks.handle_subscription_deleted")
    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_subscription_deleted_event(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        mock_handler: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should call handle_subscription_deleted for customer.subscription.deleted."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        subscription_data = {"id": "sub_123", "status": "canceled"}
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.deleted",
            subscription_data,
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.deleted"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200
        mock_handler.assert_called_once_with(subscription_data)

    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_invoice_paid_event_logged(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should handle invoice.paid event successfully."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_construct.return_value = build_webhook_payload(
            "invoice.paid",
            {"id": "in_123", "customer": "cus_123"},
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "invoice.paid"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200

    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_invoice_payment_failed_event_logged(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should handle invoice.payment_failed event successfully."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_construct.return_value = build_webhook_payload(
            "invoice.payment_failed",
            {"id": "in_123", "customer": "cus_123"},
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "invoice.payment_failed"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200

    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_trial_will_end_event_logged(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should handle customer.subscription.trial_will_end event successfully."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.trial_will_end",
            {"id": "sub_123", "customer": "cus_123"},
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.trial_will_end"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200

    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_unhandled_event_returns_200(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should return 200 for unhandled event types."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_construct.return_value = build_webhook_payload(
            "some.unknown.event",
            {"id": "obj_123"},
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "some.unknown.event"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200


@pytest.mark.django_db
class TestStripeWebhookErrorHandling:
    """Tests for webhook error handling."""

    @patch("apps.billing.webhooks.handle_subscription_created")
    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_handler_exception_returns_500(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        mock_handler: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should return 500 when handler raises exception for Stripe retry."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.created",
            {"id": "sub_123"},
        )
        mock_handler.side_effect = Exception("Database error")

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.created"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        # 500 triggers Stripe retry with exponential backoff
        assert response.status_code == 500

    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_checkout_without_subscription_handled(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        client: Client,
        webhook_url: str,
    ) -> None:
        """Should handle checkout.session.completed without subscription gracefully."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        mock_construct.return_value = build_webhook_payload(
            "checkout.session.completed",
            {"id": "cs_123"},  # No subscription field
        )

        response = client.post(
            webhook_url,
            data=json.dumps({"type": "checkout.session.completed"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )

        assert response.status_code == 200


@pytest.mark.django_db
class TestStripeWebhookIdempotency:
    """Tests for webhook idempotency."""

    @patch("apps.billing.webhooks.handle_subscription_created")
    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_handler_exception_rolls_back_idempotency_marker(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        mock_handler: MagicMock,
        client: "Client",
        webhook_url: str,
    ) -> None:
        """Should rollback ProcessedWebhook when handler fails, allowing retry."""
        from apps.core.models import ProcessedWebhook

        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        event_id = "evt_rollback_test"
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.created",
            {"id": "sub_123", "status": "active"},
            event_id=event_id,
        )

        # First request - handler raises exception
        mock_handler.side_effect = Exception("Database error")
        response1 = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.created"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )
        assert response1.status_code == 500

        # Critical: ProcessedWebhook should NOT be persisted due to rollback
        assert not ProcessedWebhook.objects.filter(source="stripe", event_id=event_id).exists()

        # Retry request - handler succeeds this time
        mock_handler.side_effect = None
        mock_handler.reset_mock()
        response2 = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.created"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )
        assert response2.status_code == 200

        # Handler should be called on retry
        assert mock_handler.call_count == 1
        # Now the marker should exist
        assert ProcessedWebhook.objects.filter(source="stripe", event_id=event_id).exists()

    @patch("apps.billing.webhooks.handle_subscription_created")
    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_duplicate_event_not_processed(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        mock_handler: MagicMock,
        client: "Client",
        webhook_url: str,
    ) -> None:
        """Should skip processing for duplicate event IDs."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        subscription_data = {"id": "sub_123", "status": "active"}
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.created",
            subscription_data,
            event_id="evt_idempotency_test",
        )

        # First request - should process
        response1 = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.created"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )
        assert response1.status_code == 200
        assert mock_handler.call_count == 1

        # Second request with same event ID - should skip
        response2 = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.created"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )
        assert response2.status_code == 200
        # Handler should NOT be called again
        assert mock_handler.call_count == 1

    @patch("apps.billing.webhooks.handle_subscription_created")
    @patch("apps.billing.webhooks.stripe.Webhook.construct_event")
    @patch("apps.billing.webhooks.settings")
    @patch("apps.billing.webhooks.get_stripe")
    def test_different_events_processed_separately(
        self,
        mock_get_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_construct: MagicMock,
        mock_handler: MagicMock,
        client: "Client",
        webhook_url: str,
    ) -> None:
        """Should process events with different IDs."""
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        subscription_data = {"id": "sub_123", "status": "active"}

        # First event
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.created",
            subscription_data,
            event_id="evt_first",
        )
        response1 = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.created"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )
        assert response1.status_code == 200

        # Second event with different ID
        mock_construct.return_value = build_webhook_payload(
            "customer.subscription.created",
            subscription_data,
            event_id="evt_second",
        )
        response2 = client.post(
            webhook_url,
            data=json.dumps({"type": "customer.subscription.created"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature",
        )
        assert response2.status_code == 200

        # Both should be processed
        assert mock_handler.call_count == 2
