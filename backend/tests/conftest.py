"""
Shared pytest fixtures for all tests.

This module provides common fixtures used across multiple test modules.
Individual test modules can override these fixtures if needed.

Factories
---------
Import factories directly from their modules:

    from tests.accounts.factories import UserFactory, OrganizationFactory, MemberFactory
    from tests.billing.factories import SubscriptionFactory
    from tests.passkeys.factories import PasskeyFactory
    from tests.webhooks.factories import WebhookEndpointFactory, WebhookDeliveryFactory

Example usage:

    @pytest.mark.django_db
    def test_something():
        user = UserFactory(email="test@example.com")
        org = OrganizationFactory()
        member = MemberFactory(user=user, organization=org, role="admin")
"""

import pytest
from django.test import Client, RequestFactory

from apps.core.auth import AuthContext


@pytest.fixture
def request_factory() -> RequestFactory:
    """
    Django request factory for unit testing views.

    Use this when you need to test view functions directly without going through
    the full HTTP stack. Useful for testing Django Ninja endpoints.

    Example:
        def test_endpoint(request_factory):
            from apps.core.auth import AuthContext
            request = request_factory.get("/api/v1/endpoint")
            request.auth = AuthContext(user=user, member=member, organization=org)
            result = my_endpoint(request)
    """
    return RequestFactory()


@pytest.fixture
def api_client() -> Client:
    """
    Django test client for full HTTP request/response cycle tests.

    Use this when you need to test the complete HTTP flow including middleware,
    routing, and response handling.

    Example:
        def test_api_returns_200(api_client):
            response = api_client.get("/api/v1/health")
            assert response.status_code == 200
    """
    return Client()


@pytest.fixture
def authenticated_request(request_factory):
    """
    Factory fixture for creating authenticated requests.

    Returns a function that creates a request with auth attributes set.
    Useful for testing authenticated endpoints.

    Example:
        def test_authenticated_endpoint(authenticated_request):
            from tests.accounts.factories import MemberFactory

            member = MemberFactory(role="admin")
            request = authenticated_request(member, method="post", path="/api/v1/something")
            result = my_endpoint(request)
    """
    from tests.accounts.factories import MemberFactory

    def _make_request(
        member=None,
        method: str = "get",
        path: str = "/",
        data: dict | None = None,
        content_type: str = "application/json",
    ):
        if member is None:
            member = MemberFactory()

        method_func = getattr(request_factory, method.lower())
        kwargs = {}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = content_type

        request = method_func(path, **kwargs)
        request.auth = AuthContext(
            user=member.user,
            member=member,
            organization=member.organization,
        )
        return request

    return _make_request


@pytest.fixture
def admin_member(db):
    """
    Create a member with admin role.

    Shortcut for tests that need an admin user.

    Example:
        def test_admin_only_action(admin_member):
            assert admin_member.role == "admin"
    """
    from tests.accounts.factories import MemberFactory

    return MemberFactory(role="admin")


@pytest.fixture
def member(db):
    """
    Create a regular member.

    Shortcut for tests that need a standard member.

    Example:
        def test_member_action(member):
            assert member.role == "member"
    """
    from tests.accounts.factories import MemberFactory

    return MemberFactory(role="member")
