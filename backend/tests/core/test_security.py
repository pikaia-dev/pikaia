"""
Tests for core security module.

Tests BearerAuth authentication class and require_admin decorator.
"""

from unittest.mock import MagicMock

import pytest
from django.http import HttpRequest, HttpResponse
from ninja.errors import HttpError

from apps.accounts.models import User
from apps.core.auth import AuthContext
from apps.core.security import BearerAuth, require_admin
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


class TestBearerAuth:
    """Tests for BearerAuth authentication class."""

    def test_authenticate_returns_token_when_auth_user_set(self) -> None:
        """Should return token when request.auth.user is populated."""
        auth = BearerAuth()
        request = HttpRequest()
        request.auth = AuthContext(user=MagicMock(spec=User))

        result = auth.authenticate(request, "test-token-123")

        assert result == "test-token-123"

    def test_authenticate_returns_none_when_auth_missing(self) -> None:
        """Should return None when request has no auth attribute."""
        auth = BearerAuth()
        request = HttpRequest()
        # No auth attribute

        result = auth.authenticate(request, "test-token-123")

        assert result is None

    def test_authenticate_returns_none_when_auth_user_is_none(self) -> None:
        """Should return None when request.auth.user is None."""
        auth = BearerAuth()
        request = HttpRequest()
        request.auth = AuthContext(user=None)

        result = auth.authenticate(request, "test-token-123")

        assert result is None


@pytest.mark.django_db
class TestRequireAdmin:
    """Tests for require_admin decorator."""

    def test_allows_admin_user(self, request_factory) -> None:
        """Should allow admin users through."""
        user = UserFactory()
        org = OrganizationFactory()
        member = MemberFactory(user=user, organization=org, role="admin")

        request = request_factory.get("/")
        request.auth = AuthContext(user=user, member=member, organization=org)

        @require_admin
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        result = view(request)
        assert result.status_code == 200

    def test_rejects_unauthenticated_user(self, request_factory) -> None:
        """Should reject unauthenticated users with 401."""
        request = request_factory.get("/")
        request.auth = AuthContext()  # No user/member/org

        @require_admin
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        with pytest.raises(HttpError) as exc:
            view(request)

        assert exc.value.status_code == 401

    def test_rejects_non_admin_user(self, request_factory) -> None:
        """Should reject non-admin users with 403."""
        user = UserFactory()
        org = OrganizationFactory()
        member = MemberFactory(user=user, organization=org, role="member")

        request = request_factory.get("/")
        request.auth = AuthContext(user=user, member=member, organization=org)

        @require_admin
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        with pytest.raises(HttpError) as exc:
            view(request)

        assert exc.value.status_code == 403


@pytest.mark.django_db
class TestGetAuthContext:
    """Tests for get_auth_context helper function."""

    def test_returns_auth_tuple(self, request_factory) -> None:
        """Should return (user, member, org) tuple when authenticated."""
        from apps.core.security import get_auth_context

        user = UserFactory()
        org = OrganizationFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.get("/")
        request.auth = AuthContext(user=user, member=member, organization=org)

        result_user, result_member, result_org = get_auth_context(request)

        assert result_user == user
        assert result_member == member
        assert result_org == org

    def test_raises_401_when_not_authenticated(self, request_factory) -> None:
        """Should raise 401 when not authenticated."""
        from apps.core.security import get_auth_context

        request = request_factory.get("/")
        request.auth = AuthContext()  # No user

        with pytest.raises(HttpError) as exc:
            get_auth_context(request)

        assert exc.value.status_code == 401
