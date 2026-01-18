"""
Tests for REST Hooks API (Zapier/Make integration).
"""

import pytest

from apps.webhooks.hooks_api import (
    get_sample,
    list_subscriptions,
    subscribe,
    unsubscribe,
    verify_auth,
)
from apps.webhooks.models import WebhookEndpoint
from apps.webhooks.schemas import RestHookSubscribeRequest
from tests.accounts.factories import MemberFactory, OrganizationFactory

pytestmark = pytest.mark.django_db


class TestAuthorization:
    """Tests for admin-only authorization on REST Hooks endpoints."""

    def test_non_admin_cannot_subscribe(self, authenticated_request):
        """Only admins can create subscriptions."""
        member = MemberFactory(role="member")  # Not admin
        request = authenticated_request(member, method="post", path="/api/v1/hooks")

        payload = RestHookSubscribeRequest(
            target_url="https://hooks.zapier.com/hooks/catch/123/abc/",
            event_type="member.created",
        )

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            subscribe(request, payload)

        assert exc_info.value.status_code == 403

    def test_non_admin_cannot_list_subscriptions(self, authenticated_request):
        """Only admins can list subscriptions."""
        member = MemberFactory(role="member")
        request = authenticated_request(member, method="get", path="/api/v1/hooks")

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            list_subscriptions(request)

        assert exc_info.value.status_code == 403

    def test_non_admin_cannot_unsubscribe(self, authenticated_request):
        """Only admins can delete subscriptions."""
        member = MemberFactory(role="member")

        endpoint = WebhookEndpoint.objects.create(
            organization=member.organization,
            name="Test Hook",
            url="https://hooks.zapier.com/test",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )

        request = authenticated_request(member, method="delete", path="/api/v1/hooks/x")

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            unsubscribe(request, endpoint.id)

        assert exc_info.value.status_code == 403
        # Endpoint should still exist
        assert WebhookEndpoint.objects.filter(id=endpoint.id).exists()


class TestSubscribe:
    """Tests for POST /api/v1/hooks (subscribe)."""

    def test_subscribe_creates_endpoint(self, authenticated_request):
        member = MemberFactory(role="admin")
        request = authenticated_request(member, method="post", path="/api/v1/hooks")

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
        assert endpoint.organization == member.organization

    def test_subscribe_detects_make_source(self, authenticated_request):
        member = MemberFactory(role="admin")
        request = authenticated_request(member, method="post", path="/api/v1/hooks")

        payload = RestHookSubscribeRequest(
            target_url="https://hook.eu1.make.com/abc123",
            event_type="member.created",
        )

        status, result = subscribe(request, payload)

        assert status == 201
        endpoint = WebhookEndpoint.objects.get(id=result.id)
        assert endpoint.source == WebhookEndpoint.Source.MAKE

    def test_subscribe_detects_generic_rest_hooks(self, authenticated_request):
        member = MemberFactory(role="admin")
        request = authenticated_request(member, method="post", path="/api/v1/hooks")

        payload = RestHookSubscribeRequest(
            target_url="https://example.com/webhook",
            event_type="member.created",
        )

        status, result = subscribe(request, payload)

        assert status == 201
        endpoint = WebhookEndpoint.objects.get(id=result.id)
        assert endpoint.source == WebhookEndpoint.Source.REST_HOOKS

    def test_subscribe_rejects_http_url(self):
        """HTTPS is required for webhook URLs."""
        with pytest.raises(ValueError, match="HTTPS"):
            RestHookSubscribeRequest(
                target_url="http://example.com/webhook",
                event_type="member.created",
            )

    def test_subscribe_rejects_invalid_event_type(self):
        """Invalid event types should be rejected."""
        with pytest.raises(ValueError, match="Invalid event type"):
            RestHookSubscribeRequest(
                target_url="https://example.com/webhook",
                event_type="invalid.event",
            )


class TestUnsubscribe:
    """Tests for DELETE /api/v1/hooks/{id} (unsubscribe)."""

    def test_unsubscribe_deletes_endpoint(self, authenticated_request):
        member = MemberFactory(role="admin")

        # Create a subscription first
        endpoint = WebhookEndpoint.objects.create(
            organization=member.organization,
            name="Test Hook",
            url="https://hooks.zapier.com/test",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )

        request = authenticated_request(member, method="delete", path="/api/v1/hooks/x")
        status, result = unsubscribe(request, endpoint.id)

        assert status == 204
        assert result is None
        assert not WebhookEndpoint.objects.filter(id=endpoint.id).exists()

    def test_unsubscribe_returns_404_for_unknown_id(self, authenticated_request):
        member = MemberFactory(role="admin")
        request = authenticated_request(member, method="delete", path="/api/v1/hooks/x")

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            unsubscribe(request, "wh_nonexistent123")

        assert exc_info.value.status_code == 404

    def test_unsubscribe_cannot_delete_other_orgs_endpoint(self, authenticated_request):
        """Endpoints belong to organizations - can't delete others'."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        member2 = MemberFactory(organization=org2, role="admin")

        # Create endpoint for org1
        endpoint = WebhookEndpoint.objects.create(
            organization=org1,
            name="Test Hook",
            url="https://hooks.zapier.com/test",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )

        # Try to delete from org2's context
        request = authenticated_request(member2, method="delete", path="/api/v1/hooks/x")

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            unsubscribe(request, endpoint.id)

        assert exc_info.value.status_code == 404
        # Endpoint should still exist
        assert WebhookEndpoint.objects.filter(id=endpoint.id).exists()


class TestListSubscriptions:
    """Tests for GET /api/v1/hooks (list)."""

    def test_list_returns_rest_hook_subscriptions(self, authenticated_request):
        member = MemberFactory(role="admin")

        # Create mixed endpoints
        _manual = WebhookEndpoint.objects.create(
            organization=member.organization,
            name="Manual Endpoint",
            url="https://example.com/webhook",
            events=["member.created"],
            source=WebhookEndpoint.Source.MANUAL,
        )
        zapier = WebhookEndpoint.objects.create(
            organization=member.organization,
            name="Zapier Hook",
            url="https://hooks.zapier.com/test",
            events=["member.created"],
            source=WebhookEndpoint.Source.ZAPIER,
        )

        request = authenticated_request(member, method="get", path="/api/v1/hooks")
        result = list_subscriptions(request)

        # Should only return REST Hook subscriptions, not manual
        assert len(result.subscriptions) == 1
        assert result.subscriptions[0].id == zapier.id

    def test_list_does_not_include_other_orgs(self, authenticated_request):
        """Subscriptions are scoped to organization."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        member1 = MemberFactory(organization=org1, role="admin")

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

        request = authenticated_request(member1, method="get", path="/api/v1/hooks")
        result = list_subscriptions(request)

        assert len(result.subscriptions) == 1
        assert result.subscriptions[0].target_url == "https://hooks.zapier.com/org1"


class TestGetSample:
    """Tests for GET /api/v1/hooks/samples/{event_type}."""

    def test_get_sample_returns_payload(self, authenticated_request):
        member = MemberFactory(role="admin")
        request = authenticated_request(
            member, method="get", path="/api/v1/hooks/samples/member.created"
        )

        result = get_sample(request, "member.created")

        assert result.event_type == "member.created"
        assert result.description != ""
        assert result.sample_payload["type"] == "member.created"
        assert "data" in result.sample_payload
        assert "organization_id" in result.sample_payload
        # Verify it uses WebhookPayload structure
        assert "spec_version" in result.sample_payload
        assert "timestamp" in result.sample_payload

    def test_get_sample_returns_404_for_unknown_event(self, authenticated_request):
        member = MemberFactory(role="admin")
        request = authenticated_request(
            member, method="get", path="/api/v1/hooks/samples/unknown.event"
        )

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            get_sample(request, "unknown.event")

        assert exc_info.value.status_code == 404


class TestAuthTest:
    """Tests for GET /api/v1/hooks/auth/test."""

    def test_auth_test_returns_org_info(self, authenticated_request):
        org = OrganizationFactory(name="Test Company")
        member = MemberFactory(organization=org, role="admin")
        request = authenticated_request(
            member, method="get", path="/api/v1/hooks/auth/test"
        )

        result = verify_auth(request)

        assert result.ok is True
        assert result.organization_id == str(org.id)
        assert result.organization_name == "Test Company"
