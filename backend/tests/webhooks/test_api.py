"""
Tests for webhook API endpoints.

Covers all webhook endpoints including authorization checks.
"""

from unittest.mock import patch

import pytest
from django.test import RequestFactory
from ninja.errors import HttpError

from apps.core.auth import AuthContext
from apps.webhooks.api import (
    create_endpoint,
    delete_endpoint,
    get_endpoint,
    list_deliveries,
    list_endpoints,
    list_events,
    send_test_webhook,
    update_endpoint,
)
from apps.webhooks.models import WebhookEndpoint
from apps.webhooks.schemas import (
    WebhookEndpointCreate,
    WebhookEndpointUpdate,
    WebhookTestRequest,
)
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory

from .factories import WebhookDeliveryFactory, WebhookEndpointFactory


def _create_authenticated_request(
    request_factory: RequestFactory,
    method: str,
    path: str,
    org=None,
    role: str = "admin",
):
    """Helper to create an authenticated request with member/org attached."""
    if org is None:
        org = OrganizationFactory()
    user = UserFactory()
    member = MemberFactory(user=user, organization=org, role=role)

    if method == "get":
        request = request_factory.get(path)
    elif method == "delete":
        request = request_factory.delete(path)
    else:
        request = request_factory.post(path)

    request.auth = AuthContext(user=user, member=member, organization=org)
    request.organization = org
    request.user = user
    return request


@pytest.mark.django_db
class TestListEvents:
    """Tests for list_events endpoint."""

    def test_returns_event_catalog(self, request_factory: RequestFactory) -> None:
        """Should return list of available events."""
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/webhooks/events", org=org
        )

        result = list_events(request)

        assert len(result.events) > 0
        assert all(hasattr(e, "type") for e in result.events)
        assert all(hasattr(e, "description") for e in result.events)
        assert all(hasattr(e, "category") for e in result.events)

    def test_includes_member_events(self, request_factory: RequestFactory) -> None:
        """Should include member events in catalog."""
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/webhooks/events", org=org
        )

        result = list_events(request)
        event_types = {e.type for e in result.events}

        assert "member.created" in event_types
        assert "member.deleted" in event_types


@pytest.mark.django_db
class TestListEndpoints:
    """Tests for list_endpoints endpoint."""

    def test_admin_can_list_endpoints(self, request_factory: RequestFactory) -> None:
        """Admin should be able to list endpoints."""
        org = OrganizationFactory()
        _ep1 = WebhookEndpointFactory(organization=org, name="Endpoint 1")
        _ep2 = WebhookEndpointFactory(organization=org, name="Endpoint 2")

        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/webhooks/endpoints", org=org, role="admin"
        )

        result = list_endpoints(request)

        assert len(result.endpoints) == 2

    def test_list_does_not_expose_secret(self, request_factory: RequestFactory) -> None:
        """List endpoint should never expose the signing secret."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/webhooks/endpoints", org=org, role="admin"
        )

        result = list_endpoints(request)

        # Verify secret is not in response
        assert len(result.endpoints) == 1
        response_dict = result.endpoints[0].model_dump()
        assert "secret" not in response_dict
        # Double-check the actual secret value isn't anywhere
        assert endpoint.secret not in str(response_dict)

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/webhooks/endpoints", org=org, role="member"
        )

        with pytest.raises(HttpError) as exc_info:
            list_endpoints(request)

        assert exc_info.value.status_code == 403

    def test_only_returns_org_endpoints(self, request_factory: RequestFactory) -> None:
        """Should only return endpoints for the authenticated org."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        _ep1 = WebhookEndpointFactory(organization=org1)
        _ep2 = WebhookEndpointFactory(organization=org2)

        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/webhooks/endpoints", org=org1, role="admin"
        )

        result = list_endpoints(request)

        assert len(result.endpoints) == 1


@pytest.mark.django_db
class TestCreateEndpoint:
    """Tests for create_endpoint endpoint."""

    def test_admin_can_create_endpoint(self, request_factory: RequestFactory) -> None:
        """Admin should be able to create endpoint."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory, "post", "/api/v1/webhooks/endpoints", org=org, role="admin"
        )
        payload = WebhookEndpointCreate(
            name="My Webhook",
            description="Test webhook",
            url="https://example.com/webhook",
            events=["member.created"],
        )

        status, result = create_endpoint(request, payload)

        assert status == 201
        assert result.name == "My Webhook"
        assert result.url == "https://example.com/webhook"
        assert result.secret.startswith("whsec_")

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory,
            "post",
            "/api/v1/webhooks/endpoints",
            org=org,
            role="member",
        )
        payload = WebhookEndpointCreate(
            name="My Webhook",
            url="https://example.com/webhook",
            events=["member.created"],
        )

        with pytest.raises(HttpError) as exc_info:
            create_endpoint(request, payload)

        assert exc_info.value.status_code == 403

    def test_endpoint_saved_to_database(self, request_factory: RequestFactory) -> None:
        """Created endpoint should be persisted."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory, "post", "/api/v1/webhooks/endpoints", org=org, role="admin"
        )
        payload = WebhookEndpointCreate(
            name="Persisted Webhook",
            url="https://example.com/webhook",
            events=["member.created"],
        )

        status, result = create_endpoint(request, payload)

        assert WebhookEndpoint.objects.filter(id=result.id).exists()
        saved = WebhookEndpoint.objects.get(id=result.id)
        assert saved.name == "Persisted Webhook"
        assert saved.organization_id == org.id


@pytest.mark.django_db
class TestGetEndpoint:
    """Tests for get_endpoint endpoint."""

    def test_admin_can_get_endpoint(self, request_factory: RequestFactory) -> None:
        """Admin should be able to get endpoint."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org, name="My Endpoint")

        request = _create_authenticated_request(
            request_factory,
            "get",
            f"/api/v1/webhooks/endpoints/{endpoint.id}",
            org=org,
            role="admin",
        )

        result = get_endpoint(request, endpoint.id)

        assert result.id == endpoint.id
        assert result.name == "My Endpoint"

    def test_get_does_not_expose_secret(self, request_factory: RequestFactory) -> None:
        """Get endpoint should never expose the signing secret."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory,
            "get",
            f"/api/v1/webhooks/endpoints/{endpoint.id}",
            org=org,
            role="admin",
        )

        result = get_endpoint(request, endpoint.id)

        # Verify secret is not in response
        response_dict = result.model_dump()
        assert "secret" not in response_dict
        # Double-check the actual secret value isn't anywhere
        assert endpoint.secret not in str(response_dict)

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory,
            "get",
            f"/api/v1/webhooks/endpoints/{endpoint.id}",
            org=org,
            role="member",
        )

        with pytest.raises(HttpError) as exc_info:
            get_endpoint(request, endpoint.id)

        assert exc_info.value.status_code == 403

    def test_returns_404_for_nonexistent(self, request_factory: RequestFactory) -> None:
        """Should return 404 for nonexistent endpoint."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory,
            "get",
            "/api/v1/webhooks/endpoints/wh_nonexistent",
            org=org,
            role="admin",
        )

        with pytest.raises(HttpError) as exc_info:
            get_endpoint(request, "wh_nonexistent")

        assert exc_info.value.status_code == 404

    def test_returns_404_for_other_org_endpoint(self, request_factory: RequestFactory) -> None:
        """Should return 404 when endpoint belongs to different org."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org2)

        request = _create_authenticated_request(
            request_factory,
            "get",
            f"/api/v1/webhooks/endpoints/{endpoint.id}",
            org=org1,
            role="admin",
        )

        with pytest.raises(HttpError) as exc_info:
            get_endpoint(request, endpoint.id)

        assert exc_info.value.status_code == 404


@pytest.mark.django_db
class TestUpdateEndpoint:
    """Tests for update_endpoint endpoint."""

    def test_admin_can_update_endpoint(self, request_factory: RequestFactory) -> None:
        """Admin should be able to update endpoint."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org, name="Old Name")

        request = _create_authenticated_request(
            request_factory,
            "post",
            f"/api/v1/webhooks/endpoints/{endpoint.id}",
            org=org,
            role="admin",
        )
        payload = WebhookEndpointUpdate(name="New Name")

        result = update_endpoint(request, endpoint.id, payload)

        assert result.name == "New Name"

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory,
            "post",
            f"/api/v1/webhooks/endpoints/{endpoint.id}",
            org=org,
            role="member",
        )
        payload = WebhookEndpointUpdate(name="New Name")

        with pytest.raises(HttpError) as exc_info:
            update_endpoint(request, endpoint.id, payload)

        assert exc_info.value.status_code == 403

    def test_partial_update_only_changes_provided_fields(
        self, request_factory: RequestFactory
    ) -> None:
        """Partial update should only change provided fields."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(
            organization=org, name="Original", description="Original desc"
        )

        request = _create_authenticated_request(
            request_factory,
            "post",
            f"/api/v1/webhooks/endpoints/{endpoint.id}",
            org=org,
            role="admin",
        )
        payload = WebhookEndpointUpdate(name="Updated")

        result = update_endpoint(request, endpoint.id, payload)

        assert result.name == "Updated"
        assert result.description == "Original desc"

    def test_returns_404_for_nonexistent(self, request_factory: RequestFactory) -> None:
        """Should return 404 for nonexistent endpoint."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory,
            "post",
            "/api/v1/webhooks/endpoints/wh_nonexistent",
            org=org,
            role="admin",
        )
        payload = WebhookEndpointUpdate(name="New Name")

        with pytest.raises(HttpError) as exc_info:
            update_endpoint(request, "wh_nonexistent", payload)

        assert exc_info.value.status_code == 404


@pytest.mark.django_db
class TestDeleteEndpoint:
    """Tests for delete_endpoint endpoint."""

    def test_admin_can_delete_endpoint(self, request_factory: RequestFactory) -> None:
        """Admin should be able to delete endpoint."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)
        endpoint_id = endpoint.id

        request = _create_authenticated_request(
            request_factory,
            "delete",
            f"/api/v1/webhooks/endpoints/{endpoint_id}",
            org=org,
            role="admin",
        )

        status, _ = delete_endpoint(request, endpoint_id)

        assert status == 204
        assert not WebhookEndpoint.objects.filter(id=endpoint_id).exists()

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory,
            "delete",
            f"/api/v1/webhooks/endpoints/{endpoint.id}",
            org=org,
            role="member",
        )

        with pytest.raises(HttpError) as exc_info:
            delete_endpoint(request, endpoint.id)

        assert exc_info.value.status_code == 403

    def test_returns_404_for_nonexistent(self, request_factory: RequestFactory) -> None:
        """Should return 404 for nonexistent endpoint."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory,
            "delete",
            "/api/v1/webhooks/endpoints/wh_nonexistent",
            org=org,
            role="admin",
        )

        with pytest.raises(HttpError) as exc_info:
            delete_endpoint(request, "wh_nonexistent")

        assert exc_info.value.status_code == 404


@pytest.mark.django_db
class TestListDeliveries:
    """Tests for list_deliveries endpoint."""

    def test_admin_can_list_deliveries(self, request_factory: RequestFactory) -> None:
        """Admin should be able to list deliveries."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)
        _delivery1 = WebhookDeliveryFactory(endpoint=endpoint)
        _delivery2 = WebhookDeliveryFactory(endpoint=endpoint)

        request = _create_authenticated_request(
            request_factory,
            "get",
            f"/api/v1/webhooks/endpoints/{endpoint.id}/deliveries",
            org=org,
            role="admin",
        )

        result = list_deliveries(request, endpoint.id)

        assert len(result.deliveries) == 2

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory,
            "get",
            f"/api/v1/webhooks/endpoints/{endpoint.id}/deliveries",
            org=org,
            role="member",
        )

        with pytest.raises(HttpError) as exc_info:
            list_deliveries(request, endpoint.id)

        assert exc_info.value.status_code == 403

    def test_returns_404_for_nonexistent_endpoint(self, request_factory: RequestFactory) -> None:
        """Should return 404 for nonexistent endpoint."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory,
            "get",
            "/api/v1/webhooks/endpoints/wh_nonexistent/deliveries",
            org=org,
            role="admin",
        )

        with pytest.raises(HttpError) as exc_info:
            list_deliveries(request, "wh_nonexistent")

        assert exc_info.value.status_code == 404

    def test_respects_limit_parameter(self, request_factory: RequestFactory) -> None:
        """Should respect limit parameter."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)
        for _ in range(10):
            WebhookDeliveryFactory(endpoint=endpoint)

        request = _create_authenticated_request(
            request_factory,
            "get",
            f"/api/v1/webhooks/endpoints/{endpoint.id}/deliveries",
            org=org,
            role="admin",
        )

        result = list_deliveries(request, endpoint.id, limit=5)

        assert len(result.deliveries) == 5


@pytest.mark.django_db
class TestSendTestWebhook:
    """Tests for send_test_webhook endpoint."""

    @patch("apps.webhooks.api.WebhookDispatcher.send_test")
    def test_admin_can_send_test(self, mock_send_test, request_factory: RequestFactory) -> None:
        """Admin should be able to send test webhook."""
        from apps.webhooks.services import DeliveryResult

        mock_send_test.return_value = DeliveryResult(
            success=True,
            http_status=200,
            duration_ms=150,
            signature="v1=test_sig",
            response_snippet='{"received": true}',
        )

        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory,
            "post",
            f"/api/v1/webhooks/endpoints/{endpoint.id}/test",
            org=org,
            role="admin",
        )
        payload = WebhookTestRequest(event_type="member.created")

        result = send_test_webhook(request, endpoint.id, payload)

        assert result.success is True
        assert result.http_status == 200
        mock_send_test.assert_called_once()

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory,
            "post",
            f"/api/v1/webhooks/endpoints/{endpoint.id}/test",
            org=org,
            role="member",
        )
        payload = WebhookTestRequest(event_type="member.created")

        with pytest.raises(HttpError) as exc_info:
            send_test_webhook(request, endpoint.id, payload)

        assert exc_info.value.status_code == 403

    def test_returns_404_for_nonexistent_endpoint(self, request_factory: RequestFactory) -> None:
        """Should return 404 for nonexistent endpoint."""
        org = OrganizationFactory()

        request = _create_authenticated_request(
            request_factory,
            "post",
            "/api/v1/webhooks/endpoints/wh_nonexistent/test",
            org=org,
            role="admin",
        )
        payload = WebhookTestRequest(event_type="member.created")

        with pytest.raises(HttpError) as exc_info:
            send_test_webhook(request, "wh_nonexistent", payload)

        assert exc_info.value.status_code == 404

    @patch("apps.webhooks.api.WebhookDispatcher.send_test")
    def test_returns_failure_result(self, mock_send_test, request_factory: RequestFactory) -> None:
        """Should return failure result when test fails."""
        from apps.webhooks.services import DeliveryResult

        mock_send_test.return_value = DeliveryResult(
            success=False,
            http_status=500,
            duration_ms=100,
            signature="v1=test_sig",
            response_snippet="Internal Server Error",
            error_type="http_error",
            error_message="HTTP 500",
        )

        org = OrganizationFactory()
        endpoint = WebhookEndpointFactory(organization=org)

        request = _create_authenticated_request(
            request_factory,
            "post",
            f"/api/v1/webhooks/endpoints/{endpoint.id}/test",
            org=org,
            role="admin",
        )
        payload = WebhookTestRequest(event_type="member.created")

        result = send_test_webhook(request, endpoint.id, payload)

        assert result.success is False
        assert result.http_status == 500
