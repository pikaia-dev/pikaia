"""
Tests for webhook services.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint
from apps.webhooks.schemas import WebhookEndpointCreate, WebhookEndpointUpdate
from apps.webhooks.services import (
    DeliveryResult,
    WebhookDispatcher,
    WebhookService,
    dispatch_event_to_subscribers,
    get_available_events,
    get_subscribed_endpoints,
)

from ..accounts.factories import OrganizationFactory, UserFactory
from .factories import WebhookDeliveryFactory, WebhookEndpointFactory


@pytest.mark.django_db
class TestWebhookService:
    """Tests for WebhookService class."""

    def test_list_endpoints(self) -> None:
        """Should list all endpoints for organization."""
        org = OrganizationFactory.create()
        other_org = OrganizationFactory.create()

        ep1 = WebhookEndpointFactory.create(organization=org)
        ep2 = WebhookEndpointFactory.create(organization=org)
        _other_ep = WebhookEndpointFactory.create(organization=other_org)

        service = WebhookService(org)
        endpoints = service.list_endpoints()

        assert len(endpoints) == 2
        assert {e.id for e in endpoints} == {ep1.id, ep2.id}

    def test_get_endpoint(self) -> None:
        """Should get endpoint by ID."""
        org = OrganizationFactory.create()
        endpoint = WebhookEndpointFactory.create(organization=org)

        service = WebhookService(org)
        result = service.get_endpoint(endpoint.id)

        assert result is not None
        assert result.id == endpoint.id

    def test_get_endpoint_wrong_org(self) -> None:
        """Should not return endpoint from different org."""
        org = OrganizationFactory.create()
        other_org = OrganizationFactory.create()
        endpoint = WebhookEndpointFactory.create(organization=other_org)

        service = WebhookService(org)
        result = service.get_endpoint(endpoint.id)

        assert result is None

    def test_create_endpoint(self) -> None:
        """Should create new endpoint."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        service = WebhookService(org)

        data = WebhookEndpointCreate(
            name="Test Webhook",
            description="Test description",
            url="https://example.com/webhook",
            events=["member.created"],
        )
        endpoint = service.create_endpoint(data, created_by_id=user.id)

        assert endpoint.name == "Test Webhook"
        assert endpoint.description == "Test description"
        assert endpoint.url == "https://example.com/webhook"
        assert endpoint.events == ["member.created"]
        assert endpoint.organization_id == org.id
        assert endpoint.created_by_id == user.id

    def test_update_endpoint(self) -> None:
        """Should update endpoint fields."""
        org = OrganizationFactory.create()
        endpoint = WebhookEndpointFactory.create(organization=org, name="Old Name")

        service = WebhookService(org)
        data = WebhookEndpointUpdate(name="New Name", active=False)
        result = service.update_endpoint(endpoint.id, data)

        assert result is not None
        assert result.name == "New Name"
        assert result.active is False

    def test_update_endpoint_partial(self) -> None:
        """Should only update provided fields."""
        org = OrganizationFactory.create()
        endpoint = WebhookEndpointFactory.create(
            organization=org,
            name="Original",
            description="Original desc",
        )

        service = WebhookService(org)
        data = WebhookEndpointUpdate(name="Updated")  # Only update name
        result = service.update_endpoint(endpoint.id, data)

        assert result is not None
        assert result.name == "Updated"
        assert result.description == "Original desc"

    def test_delete_endpoint(self) -> None:
        """Should delete endpoint."""
        org = OrganizationFactory.create()
        endpoint = WebhookEndpointFactory.create(organization=org)

        service = WebhookService(org)
        result = service.delete_endpoint(endpoint.id)

        assert result is True
        assert not WebhookEndpoint.objects.filter(id=endpoint.id).exists()

    def test_delete_endpoint_wrong_org(self) -> None:
        """Should not delete endpoint from different org."""
        org = OrganizationFactory.create()
        other_org = OrganizationFactory.create()
        endpoint = WebhookEndpointFactory.create(organization=other_org)

        service = WebhookService(org)
        result = service.delete_endpoint(endpoint.id)

        assert result is False
        assert WebhookEndpoint.objects.filter(id=endpoint.id).exists()

    def test_list_deliveries(self) -> None:
        """Should list deliveries for endpoint."""
        org = OrganizationFactory.create()
        endpoint = WebhookEndpointFactory.create(organization=org)
        # Create deliveries to verify they're returned
        _delivery1 = WebhookDeliveryFactory.create(endpoint=endpoint)
        _delivery2 = WebhookDeliveryFactory.create(endpoint=endpoint)

        service = WebhookService(org)
        deliveries = service.list_deliveries(endpoint.id)

        assert len(deliveries) == 2


@pytest.mark.django_db
class TestWebhookDispatcher:
    """Tests for WebhookDispatcher class."""

    def test_dispatch_success(self) -> None:
        """Should return success result on 200 response."""
        endpoint = WebhookEndpointFactory.create()
        dispatcher = WebhookDispatcher()

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"received": true}'
            mock_post.return_value = mock_response

            result = dispatcher.dispatch(
                endpoint=endpoint,
                event_id="evt_test_123",
                event_type="member.created",
                event_data={"email": "test@example.com"},
                organization_id=str(endpoint.organization_id),
            )

        assert result.success is True
        assert result.http_status == 200
        assert result.duration_ms >= 0
        assert result.signature.startswith("v1=")

    def test_dispatch_failure_http_error(self) -> None:
        """Should return failure result on non-2xx response."""
        endpoint = WebhookEndpointFactory.create()
        dispatcher = WebhookDispatcher()

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_post.return_value = mock_response

            result = dispatcher.dispatch(
                endpoint=endpoint,
                event_id="evt_test_123",
                event_type="member.created",
                event_data={},
                organization_id=str(endpoint.organization_id),
            )

        assert result.success is False
        assert result.http_status == 500
        assert result.error_type == WebhookDelivery.ErrorType.HTTP_ERROR

    def test_dispatch_failure_timeout(self) -> None:
        """Should return failure result on timeout."""
        endpoint = WebhookEndpointFactory.create()
        dispatcher = WebhookDispatcher(timeout=1)

        with patch.object(httpx.Client, "post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")

            result = dispatcher.dispatch(
                endpoint=endpoint,
                event_id="evt_test_123",
                event_type="member.created",
                event_data={},
                organization_id=str(endpoint.organization_id),
            )

        assert result.success is False
        assert result.http_status is None
        assert result.error_type == WebhookDelivery.ErrorType.TIMEOUT

    def test_dispatch_failure_connection_error(self) -> None:
        """Should return failure result on connection error."""
        endpoint = WebhookEndpointFactory.create()
        dispatcher = WebhookDispatcher()

        with patch.object(httpx.Client, "post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            result = dispatcher.dispatch(
                endpoint=endpoint,
                event_id="evt_test_123",
                event_type="member.created",
                event_data={},
                organization_id=str(endpoint.organization_id),
            )

        assert result.success is False
        assert result.http_status is None
        assert result.error_type == WebhookDelivery.ErrorType.CONNECTION_ERROR

    def test_send_test_uses_example_payload(self) -> None:
        """Should use example payload from event catalog."""
        endpoint = WebhookEndpointFactory.create()
        dispatcher = WebhookDispatcher()

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = ""
            mock_post.return_value = mock_response

            result = dispatcher.send_test(endpoint, "member.created")

        assert result.success is True
        # Verify the call was made with correct content type
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["Content-Type"] == "application/json"

    def test_send_test_invalid_event(self) -> None:
        """Should return error for invalid event type."""
        endpoint = WebhookEndpointFactory.create()
        dispatcher = WebhookDispatcher()

        result = dispatcher.send_test(endpoint, "invalid.event")

        assert result.success is False
        assert result.error_type == "invalid_event"


@pytest.mark.django_db
class TestGetSubscribedEndpoints:
    """Tests for get_subscribed_endpoints function."""

    def test_returns_matching_endpoints(self) -> None:
        """Should return endpoints subscribed to event."""
        org = OrganizationFactory.create()
        ep1 = WebhookEndpointFactory.create(
            organization=org,
            events=["member.created"],
            active=True,
        )
        ep2 = WebhookEndpointFactory.create(
            organization=org,
            events=["member.*"],
            active=True,
        )
        _ep3 = WebhookEndpointFactory.create(
            organization=org,
            events=["billing.payment_succeeded"],
            active=True,
        )

        endpoints = get_subscribed_endpoints(str(org.id), "member.created")

        assert len(endpoints) == 2
        assert {e.id for e in endpoints} == {ep1.id, ep2.id}

    def test_excludes_inactive_endpoints(self) -> None:
        """Should not return inactive endpoints."""
        org = OrganizationFactory.create()
        _inactive = WebhookEndpointFactory.create(
            organization=org,
            events=["member.created"],
            active=False,
        )

        endpoints = get_subscribed_endpoints(str(org.id), "member.created")

        assert len(endpoints) == 0

    def test_filters_by_organization(self) -> None:
        """Should only return endpoints for specified org."""
        org1 = OrganizationFactory.create()
        org2 = OrganizationFactory.create()
        ep1 = WebhookEndpointFactory.create(organization=org1, events=["member.created"])
        _ep2 = WebhookEndpointFactory.create(organization=org2, events=["member.created"])

        endpoints = get_subscribed_endpoints(str(org1.id), "member.created")

        assert len(endpoints) == 1
        assert endpoints[0].id == ep1.id


@pytest.mark.django_db
class TestDispatchEventToSubscribers:
    """Tests for dispatch_event_to_subscribers function."""

    def test_dispatches_to_all_subscribers(self) -> None:
        """Should dispatch to all subscribed endpoints."""
        org = OrganizationFactory.create()
        # Create endpoints to receive webhooks
        _ep1 = WebhookEndpointFactory.create(organization=org, events=["member.created"])
        _ep2 = WebhookEndpointFactory.create(organization=org, events=["member.*"])

        with patch("apps.webhooks.services.WebhookDispatcher.dispatch") as mock_dispatch:
            mock_dispatch.return_value = DeliveryResult(
                success=True,
                http_status=200,
                duration_ms=100,
                response_snippet="",
                signature="v1=test",
            )

            results = dispatch_event_to_subscribers(
                organization_id=str(org.id),
                event_id="evt_123",
                event_type="member.created",
                event_data={"email": "test@example.com"},
            )

        assert len(results) == 2
        assert mock_dispatch.call_count == 2

    def test_creates_delivery_records(self) -> None:
        """Should create delivery records for each endpoint."""
        org = OrganizationFactory.create()
        WebhookEndpointFactory.create(organization=org, events=["member.created"])

        with patch("apps.webhooks.services.WebhookDispatcher.dispatch") as mock_dispatch:
            mock_dispatch.return_value = DeliveryResult(
                success=True,
                http_status=200,
                duration_ms=100,
                response_snippet="",
                signature="v1=test",
            )

            dispatch_event_to_subscribers(
                organization_id=str(org.id),
                event_id="evt_unique_456",
                event_type="member.created",
                event_data={},
            )

        assert WebhookDelivery.objects.filter(event_id="evt_unique_456").count() == 1

    def test_skips_already_delivered(self) -> None:
        """Should skip events already successfully delivered."""
        org = OrganizationFactory.create()
        endpoint = WebhookEndpointFactory.create(organization=org, events=["member.created"])

        # Pre-create successful delivery
        WebhookDeliveryFactory.create(
            endpoint=endpoint,
            event_id="evt_already_done",
            status=WebhookDelivery.Status.SUCCESS,
        )

        with patch("apps.webhooks.services.WebhookDispatcher.dispatch") as mock_dispatch:
            results = dispatch_event_to_subscribers(
                organization_id=str(org.id),
                event_id="evt_already_done",
                event_type="member.created",
                event_data={},
            )

        assert len(results) == 0
        mock_dispatch.assert_not_called()


class TestGetAvailableEvents:
    """Tests for get_available_events function."""

    def test_returns_event_list(self) -> None:
        """Should return list of event dictionaries."""
        events = get_available_events()

        assert len(events) > 0
        assert all("type" in e for e in events)
        assert all("description" in e for e in events)
        assert all("category" in e for e in events)
        assert all("payload_example" in e for e in events)

    def test_includes_member_events(self) -> None:
        """Should include member events."""
        events = get_available_events()
        types = {e["type"] for e in events}

        assert "member.created" in types
        assert "member.deleted" in types
