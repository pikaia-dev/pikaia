"""
Tests for webhook models.
"""

import pytest

from apps.webhooks.models import (
    WebhookDelivery,
    generate_delivery_id,
    generate_webhook_id,
    generate_webhook_secret,
)

from .factories import WebhookDeliveryFactory, WebhookEndpointFactory


class TestGenerators:
    """Tests for ID and secret generators."""

    def test_webhook_id_has_prefix(self) -> None:
        """Should generate ID with wh_ prefix."""
        id_ = generate_webhook_id()

        assert id_.startswith("wh_")

    def test_delivery_id_has_prefix(self) -> None:
        """Should generate ID with del_ prefix."""
        id_ = generate_delivery_id()

        assert id_.startswith("del_")

    def test_webhook_secret_has_prefix(self) -> None:
        """Should generate secret with whsec_ prefix."""
        secret = generate_webhook_secret()

        assert secret.startswith("whsec_")

    def test_generated_ids_are_unique(self) -> None:
        """Generated IDs should be unique."""
        ids = {generate_webhook_id() for _ in range(100)}

        assert len(ids) == 100

    def test_generated_secrets_are_unique(self) -> None:
        """Generated secrets should be unique."""
        secrets = {generate_webhook_secret() for _ in range(100)}

        assert len(secrets) == 100


@pytest.mark.django_db
class TestWebhookEndpoint:
    """Tests for WebhookEndpoint model."""

    def test_creates_with_defaults(self) -> None:
        """Should create endpoint with default values."""
        endpoint = WebhookEndpointFactory.create()

        assert endpoint.active is True
        assert endpoint.consecutive_failures == 0
        assert endpoint.last_delivery_status == ""
        assert endpoint.last_delivery_at is None
        assert endpoint.secret.startswith("whsec_")

    def test_regenerate_secret(self) -> None:
        """Should generate new secret and save."""
        endpoint = WebhookEndpointFactory.create()
        old_secret = endpoint.secret

        new_secret = endpoint.regenerate_secret()

        endpoint.refresh_from_db()
        assert new_secret != old_secret
        assert endpoint.secret == new_secret

    def test_record_delivery_success(self) -> None:
        """Should update status on delivery success."""
        endpoint = WebhookEndpointFactory.create(consecutive_failures=3)

        endpoint.record_delivery_success()

        endpoint.refresh_from_db()
        assert endpoint.last_delivery_status == "success"
        assert endpoint.last_delivery_at is not None
        assert endpoint.consecutive_failures == 0

    def test_record_delivery_failure(self) -> None:
        """Should increment failures on delivery failure."""
        endpoint = WebhookEndpointFactory.create(consecutive_failures=2)

        endpoint.record_delivery_failure()

        endpoint.refresh_from_db()
        assert endpoint.last_delivery_status == "failure"
        assert endpoint.last_delivery_at is not None
        assert endpoint.consecutive_failures == 3


@pytest.mark.django_db
class TestWebhookDelivery:
    """Tests for WebhookDelivery model."""

    def test_creates_with_defaults(self) -> None:
        """Should create delivery with default values."""
        delivery = WebhookDeliveryFactory.create()

        assert delivery.status == WebhookDelivery.Status.PENDING
        assert delivery.attempt_number == 1
        assert delivery.error_type == ""

    def test_mark_success(self) -> None:
        """Should mark delivery as successful."""
        delivery = WebhookDeliveryFactory.create()

        delivery.mark_success(
            http_status=200,
            duration_ms=150,
            response_snippet='{"received": true}',
        )

        delivery.refresh_from_db()
        assert delivery.status == WebhookDelivery.Status.SUCCESS
        assert delivery.http_status == 200
        assert delivery.duration_ms == 150
        assert delivery.response_snippet == '{"received": true}'
        assert delivery.next_retry_at is None

    def test_mark_failure_schedules_retry(self) -> None:
        """Should schedule retry on failure."""
        delivery = WebhookDeliveryFactory.create(attempt_number=1)

        delivery.mark_failure(
            error_type=WebhookDelivery.ErrorType.HTTP_ERROR,
            error_message="HTTP 500",
            http_status=500,
        )

        delivery.refresh_from_db()
        assert delivery.status == WebhookDelivery.Status.PENDING
        assert delivery.attempt_number == 2
        assert delivery.next_retry_at is not None
        assert delivery.error_type == WebhookDelivery.ErrorType.HTTP_ERROR

    def test_mark_failure_terminal_no_retry(self) -> None:
        """Should not retry on terminal failure."""
        delivery = WebhookDeliveryFactory.create(attempt_number=1)

        delivery.mark_failure(
            error_type=WebhookDelivery.ErrorType.HTTP_ERROR,
            error_message="HTTP 410 Gone",
            http_status=410,
        )

        delivery.refresh_from_db()
        assert delivery.status == WebhookDelivery.Status.FAILURE
        assert delivery.next_retry_at is None

    def test_mark_failure_after_max_attempts(self) -> None:
        """Should fail permanently after max attempts."""
        delivery = WebhookDeliveryFactory.create(attempt_number=6)  # At max

        delivery.mark_failure(
            error_type=WebhookDelivery.ErrorType.TIMEOUT,
            error_message="Request timed out",
        )

        delivery.refresh_from_db()
        assert delivery.status == WebhookDelivery.Status.FAILURE
        assert delivery.next_retry_at is None

    def test_create_for_event_is_idempotent(self) -> None:
        """Should return existing delivery if already exists."""
        endpoint = WebhookEndpointFactory.create()
        event_id = "evt_test_123"

        delivery1 = WebhookDelivery.create_for_event(
            endpoint=endpoint,
            event_id=event_id,
            event_type="member.created",
        )
        delivery2 = WebhookDelivery.create_for_event(
            endpoint=endpoint,
            event_id=event_id,
            event_type="member.created",
        )

        assert delivery1.id == delivery2.id
        assert WebhookDelivery.objects.count() == 1

    def test_truncates_long_response_snippet(self) -> None:
        """Should truncate response snippets over 500 chars."""
        delivery = WebhookDeliveryFactory.create()
        long_response = "x" * 1000

        delivery.mark_success(
            http_status=200,
            duration_ms=100,
            response_snippet=long_response,
        )

        delivery.refresh_from_db()
        assert len(delivery.response_snippet) == 500

    def test_retry_delays_are_exponential(self) -> None:
        """Retry delays should follow exponential backoff."""
        delays = WebhookDelivery.RETRY_DELAYS_SECONDS

        # First retry should be immediate
        assert delays[0] == 0

        # Subsequent retries should increase
        assert delays[1] < delays[2] < delays[3] < delays[4] < delays[5]

        # Final retry should be 8 hours
        assert delays[5] == 8 * 60 * 60


@pytest.mark.django_db
class TestUniqueConstraint:
    """Tests for the unique constraint on (event_id, endpoint)."""

    def test_allows_same_event_to_different_endpoints(self) -> None:
        """Should allow same event to be delivered to different endpoints."""
        endpoint1 = WebhookEndpointFactory.create()
        endpoint2 = WebhookEndpointFactory.create()
        event_id = "evt_shared_123"

        delivery1 = WebhookDeliveryFactory.create(endpoint=endpoint1, event_id=event_id)
        delivery2 = WebhookDeliveryFactory.create(endpoint=endpoint2, event_id=event_id)

        assert delivery1.id != delivery2.id
        assert WebhookDelivery.objects.filter(event_id=event_id).count() == 2

    def test_prevents_duplicate_delivery_to_same_endpoint(self) -> None:
        """Should prevent duplicate deliveries to same endpoint."""
        endpoint = WebhookEndpointFactory.create()
        event_id = "evt_unique_123"

        WebhookDeliveryFactory.create(endpoint=endpoint, event_id=event_id)

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            WebhookDeliveryFactory.create(endpoint=endpoint, event_id=event_id)
