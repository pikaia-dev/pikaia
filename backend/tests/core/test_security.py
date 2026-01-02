"""
Tests for core security module.

Tests BearerAuth authentication class and require_admin decorator.
"""

from unittest.mock import MagicMock

import pytest
from django.http import HttpRequest, HttpResponse
from ninja.errors import HttpError

from apps.accounts.models import User
from apps.core.security import BearerAuth, require_admin
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


class TestBearerAuth:
    """Tests for BearerAuth authentication class."""

    def test_authenticate_returns_token_when_auth_user_set(self) -> None:
        """Should return token when request.auth_user is populated."""
        auth = BearerAuth()
        request = HttpRequest()
        request.auth_user = MagicMock(spec=User)  # type: ignore[attr-defined]

        result = auth.authenticate(request, "test-token-123")

        assert result == "test-token-123"

    def test_authenticate_returns_none_when_auth_user_missing(self) -> None:
        """Should return None when request has no auth_user attribute."""
        auth = BearerAuth()
        request = HttpRequest()
        # No auth_user attribute

        result = auth.authenticate(request, "test-token-123")

        assert result is None

    def test_authenticate_returns_none_when_auth_user_is_none(self) -> None:
        """Should return None when request.auth_user is None."""
        auth = BearerAuth()
        request = HttpRequest()
        request.auth_user = None  # type: ignore[attr-defined]

        result = auth.authenticate(request, "test-token-123")

        assert result is None


@pytest.mark.django_db
class TestRequireAdmin:
    """Tests for require_admin decorator."""

    def test_allows_admin_user(self) -> None:
        """Should allow admin user to access endpoint."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="admin")

        # Create request with auth context
        request = HttpRequest()
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        # Create decorated function
        @require_admin
        def protected_endpoint(request: HttpRequest) -> HttpResponse:
            return HttpResponse("Success")

        # Should not raise
        response = protected_endpoint(request)
        assert response.content == b"Success"

    def test_raises_401_for_unauthenticated(self) -> None:
        """Should raise 401 when user is not authenticated."""
        request = HttpRequest()
        # No auth context

        @require_admin
        def protected_endpoint(request: HttpRequest) -> HttpResponse:
            return HttpResponse("Success")

        with pytest.raises(HttpError) as exc_info:
            protected_endpoint(request)

        assert exc_info.value.status_code == 401
        assert "Not authenticated" in str(exc_info.value.message)

    def test_raises_401_when_auth_member_is_none(self) -> None:
        """Should raise 401 when auth_member is explicitly None."""
        request = HttpRequest()
        request.auth_member = None  # type: ignore[attr-defined]

        @require_admin
        def protected_endpoint(request: HttpRequest) -> HttpResponse:
            return HttpResponse("Success")

        with pytest.raises(HttpError) as exc_info:
            protected_endpoint(request)

        assert exc_info.value.status_code == 401

    def test_raises_403_for_non_admin(self) -> None:
        """Should raise 403 when user is not an admin."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="member")

        request = HttpRequest()
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        @require_admin
        def protected_endpoint(request: HttpRequest) -> HttpResponse:
            return HttpResponse("Success")

        with pytest.raises(HttpError) as exc_info:
            protected_endpoint(request)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in str(exc_info.value.message)

    def test_passes_through_args_and_kwargs(self) -> None:
        """Should pass arguments through to wrapped function."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="admin")

        request = HttpRequest()
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        @require_admin
        def endpoint_with_args(
            request: HttpRequest, arg1: str, arg2: int, kwarg1: str = "default"
        ) -> dict:
            return {"arg1": arg1, "arg2": arg2, "kwarg1": kwarg1}

        result = endpoint_with_args(request, "value1", 42, kwarg1="custom")

        assert result == {"arg1": "value1", "arg2": 42, "kwarg1": "custom"}
