"""
Tests for REST Hooks API (Zapier/Make integration).
"""

import pytest
from django.test import RequestFactory

from apps.webhooks.hooks_api import (
    get_sample,
    list_subscriptions,
    subscribe,
    unsubscribe,
    verify_auth,
)
from apps.webhooks.models import WebhookEndpoint
from apps.webhooks.schemas import RestHookSubscribeRequest
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory

pytestmark = pytest.mark.django_db


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

    request.auth_user = user
    request.auth_member = member
    request.auth_organization = org
    return request


class TestSubscribe:
    """Tests for POST /api/v1/hooks (subscribe)."""

    def test_subscribe_creates_endpoint(self, request_factory: RequestFactory):
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "post", "/api/v1/hooks", org=org
        )

        payload = RestHookSubscribeRequest(
            target_url="https://hooks.zapier.com/hooks/catch/123/abc/",
            event_type="member.created",
        )

        status, result = subscribe(request, payload)

        assert status == 201
        assert result.target_url == "https://hooks.zapier.com/hooks/catch/123/abc/"
        assert result.event_type == "member.created"
        assert result.status == "active"

        # Verify endpoint was created in DB
        endpoint = WebhookEndpoint.objects.get(id=result.id)
        assert endpoint.source == WebhookEndpoint.Source.ZAPIER
        assert endpoint.organization == org

    def test_subscribe_detects_make_source(self, request_factory: RequestFactory):
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "post", "/api/v1/hooks", org=org
        )

        payload = RestHookSubscribeRequest(
            target_url="https://hook.eu1.make.com/abc123",
            event_type="member.created",
        )

        status, result = subscribe(request, payload)

        assert status == 201
        endpoint = WebhookEndpoint.objects.get(id=result.id)
        assert endpoint.source == WebhookEndpoint.Source.MAKE

    def test_subscribe_detects_generic_rest_hooks(self, request_factory: RequestFactory):
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "post", "/api/v1/hooks", org=org
        )

        payload = RestHookSubscribeRequest(
            target_url="https://example.com/webhook",
            event_type="member.created",
        )

        status, result = subscribe(request, payload)

        assert status == 201
        endpoint = WebhookEndpoint.objects.get(id=result.id)
        assert endpoint.source == WebhookEndpoint.Source.REST_HOOKS

    def test_subscribe_rejects_http_url(self, request_factory: RequestFactory):
        """HTTPS is required for webhook URLs."""
        with pytest.raises(ValueError, match="HTTPS"):
            RestHookSubscribeRequest(
                target_url="http://example.com/webhook",
                event_type="member.created",
            )

    def test_subscribe_rejects_invalid_event_type(self, request_factory: RequestFactory):
        """Invalid event types should be rejected."""
        with pytest.raises(ValueError, match="Invalid event type"):
            RestHookSubscribeRequest(
                target_url="https://example.com/webhook",
                event_type="invalid.event",
            )


class TestUnsubscribe:
    """Tests for DELETE /api/v1/hooks/{id} (unsubscribe)."""

    def test_unsubscribe_deletes_endpoint(self, request_factory: RequestFactory):
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "delete", "/api/v1/hooks/test", org=org
        )

        # Create a subscription first
        endpoint = WebhookEndpoint.objects.create(
            organization=org,
            name="Test Hook",
            url="https://hooks.zapier.com/test",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )

        status, result = unsubscribe(request, endpoint.id)

        assert status == 204
        assert result is None
        assert not WebhookEndpoint.objects.filter(id=endpoint.id).exists()

    def test_unsubscribe_returns_404_for_unknown_id(self, request_factory: RequestFactory):
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "delete", "/api/v1/hooks/test", org=org
        )

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            unsubscribe(request, "wh_nonexistent123")

        assert exc_info.value.status_code == 404

    def test_unsubscribe_cannot_delete_other_orgs_endpoint(
        self, request_factory: RequestFactory
    ):
        """Endpoints belong to organizations - can't delete others'."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        # Create endpoint for org1
        endpoint = WebhookEndpoint.objects.create(
            organization=org1,
            name="Test Hook",
            url="https://hooks.zapier.com/test",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )

        # Try to delete from org2's context
        request = _create_authenticated_request(
            request_factory, "delete", "/api/v1/hooks/test", org=org2
        )

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            unsubscribe(request, endpoint.id)

        assert exc_info.value.status_code == 404
        # Endpoint should still exist
        assert WebhookEndpoint.objects.filter(id=endpoint.id).exists()


class TestListSubscriptions:
    """Tests for GET /api/v1/hooks (list)."""

    def test_list_returns_rest_hook_subscriptions(self, request_factory: RequestFactory):
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/hooks", org=org
        )

        # Create mixed endpoints
        _manual = WebhookEndpoint.objects.create(
            organization=org,
            name="Manual Endpoint",
            url="https://example.com/webhook",
            events=["member.created"],
            source=WebhookEndpoint.Source.MANUAL,
        )
        zapier = WebhookEndpoint.objects.create(
            organization=org,
            name="Zapier Hook",
            url="https://hooks.zapier.com/test",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )

        result = list_subscriptions(request)

        # Should only return REST Hook subscriptions, not manual
        assert len(result.subscriptions) == 1
        assert result.subscriptions[0].id == zapier.id

    def test_list_does_not_include_other_orgs(self, request_factory: RequestFactory):
        """Subscriptions are scoped to organization."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        # Create endpoints for each org
        _ep1 = WebhookEndpoint.objects.create(
            organization=org1,
            name="Org1 Hook",
            url="https://hooks.zapier.com/org1",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )
        _ep2 = WebhookEndpoint.objects.create(
            organization=org2,
            name="Org2 Hook",
            url="https://hooks.zapier.com/org2",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )

        # Request from org1
        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/hooks", org=org1
        )
        result = list_subscriptions(request)

        assert len(result.subscriptions) == 1
        assert result.subscriptions[0].target_url == "https://hooks.zapier.com/org1"


class TestGetSample:
    """Tests for GET /api/v1/hooks/samples/{event_type}."""

    def test_get_sample_returns_payload(self, request_factory: RequestFactory):
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/hooks/samples/member.created", org=org
        )

        result = get_sample(request, "member.created")

        assert result.event_type == "member.created"
        assert result.description != ""
        assert "type" in result.sample_payload
        assert result.sample_payload["type"] == "member.created"
        assert "data" in result.sample_payload
        assert "organization_id" in result.sample_payload

    def test_get_sample_returns_404_for_unknown_event(
        self, request_factory: RequestFactory
    ):
        org = OrganizationFactory()
        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/hooks/samples/unknown.event", org=org
        )

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            get_sample(request, "unknown.event")

        assert exc_info.value.status_code == 404


class TestAuthTest:
    """Tests for GET /api/v1/hooks/auth/test."""

    def test_auth_test_returns_org_info(self, request_factory: RequestFactory):
        org = OrganizationFactory(name="Test Company")
        request = _create_authenticated_request(
            request_factory, "get", "/api/v1/hooks/auth/test", org=org
        )

        result = verify_auth(request)

        assert result.ok is True
        assert result.organization_id == str(org.id)
        assert result.organization_name == "Test Company"
