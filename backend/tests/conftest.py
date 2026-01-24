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
        user = UserFactory.create(email="test@example.com")
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org, role="admin")
"""

from collections.abc import Callable
from typing import Any, cast

import pytest
from django.db import connection
from django.http import HttpRequest
from django.test import Client, RequestFactory
from django.test.client import WSGIRequest  # type: ignore[attr-defined]

from apps.core.auth import AuthContext
from apps.core.types import AuthenticatedHttpRequest


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Create and teardown test model tables in the database.

    This extends pytest-django's django_db_setup to create tables for
    test-only models like SyncTestContact that aren't managed by migrations.
    """
    from tests.sync.conftest import SyncTestContact

    with django_db_blocker.unblock(), connection.schema_editor() as schema_editor:
        if SyncTestContact._meta.db_table not in connection.introspection.table_names():
            schema_editor.create_model(SyncTestContact)

    yield

    # Cleanup: drop the table at session end
    with django_db_blocker.unblock(), connection.schema_editor() as schema_editor:
        if SyncTestContact._meta.db_table in connection.introspection.table_names():
            schema_editor.delete_model(SyncTestContact)


class MockRequest(HttpRequest):
    """
    HttpRequest subclass for tests that allows setting auth attribute.

    Use this instead of HttpRequest() in tests that need to set request.auth.

    Example:
        request = MockRequest()
        request.auth = AuthContext(user=user, member=member, organization=org)
    """

    auth: AuthContext


class MockWSGIRequest(AuthenticatedHttpRequest):
    """
    Test request type compatible with AuthenticatedHttpRequest.

    RequestFactory returns WSGIRequest, so we cast to this type after
    setting auth. This type extends AuthenticatedHttpRequest to be
    compatible with API endpoint signatures.
    """

    organization: Any
    user: Any


def make_request_with_auth(request: "WSGIRequest", auth: AuthContext) -> AuthenticatedHttpRequest:
    """
    Set auth on a request and return it typed as AuthenticatedHttpRequest.

    Use this helper to set request.auth while satisfying mypy.
    Returns AuthenticatedHttpRequest for compatibility with API endpoints.

    Example:
        request = request_factory.get("/api/v1/endpoint")
        request = make_request_with_auth(request, AuthContext(user=user, member=member))
    """
    request.auth = auth  # type: ignore[attr-defined]
    return cast(AuthenticatedHttpRequest, request)


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
def authenticated_request(
    request_factory: RequestFactory,
) -> Callable[..., AuthenticatedHttpRequest]:
    """
    Factory fixture for creating authenticated requests.

    Returns a function that creates a request with auth attributes set.
    Useful for testing authenticated endpoints.

    Example:
        def test_authenticated_endpoint(authenticated_request):
            from tests.accounts.factories import MemberFactory

            member = MemberFactory.create(role="admin")
            request = authenticated_request(member, method="post", path="/api/v1/something")
            result = my_endpoint(request)
    """
    from tests.accounts.factories import MemberFactory

    def _make_request(
        member: Any = None,
        method: str = "get",
        path: str = "/",
        data: dict | None = None,
        content_type: str = "application/json",
    ) -> AuthenticatedHttpRequest:
        if member is None:
            member = MemberFactory.create()

        method_func = getattr(request_factory, method.lower())
        kwargs: dict[str, Any] = {}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = content_type

        request = method_func(path, **kwargs)
        return make_request_with_auth(
            request,
            AuthContext(
                user=member.user,
                member=member,
                organization=member.organization,
            ),
        )

    return _make_request


def create_authenticated_request(
    request_factory: RequestFactory,
    method: str,
    path: str,
    org: Any = None,
    role: str = "admin",
) -> AuthenticatedHttpRequest:
    """
    Helper to create an authenticated request with member/org attached.

    Creates organization, user, and member if not provided.
    Sets request.auth with AuthContext and legacy attributes (user, organization).

    Args:
        request_factory: Django RequestFactory instance
        method: HTTP method (get, post, delete, patch, put)
        path: Request path
        org: Optional Organization instance (created if None)
        role: Member role (default: "admin")

    Returns:
        Request object with auth attributes set
    """
    from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory

    if org is None:
        org = OrganizationFactory.create()
    user = UserFactory.create()
    member = MemberFactory.create(user=user, organization=org, role=role)

    method_func = getattr(request_factory, method.lower())
    request = method_func(path)

    typed_request = make_request_with_auth(
        request, AuthContext(user=user, member=member, organization=org)
    )
    # Legacy attributes for backward compatibility
    typed_request.organization = org  # type: ignore[attr-defined]
    typed_request.user = user
    return typed_request


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

    return MemberFactory.create(role="admin")


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

    return MemberFactory.create(role="member")
