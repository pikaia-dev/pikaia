"""
Tests for core security module.

Tests BearerAuth authentication class, require_admin, and require_subscription decorators.
"""

from unittest.mock import MagicMock

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import override_settings
from ninja.errors import HttpError

from apps.accounts.models import User
from apps.billing.models import Subscription
from apps.core.auth import AuthContext
from apps.core.security import BearerAuth, require_admin, require_subscription
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory
from tests.billing.factories import SubscriptionFactory
from tests.conftest import MockRequest, make_request_with_auth


class TestBearerAuth:
    """Tests for BearerAuth authentication class."""

    def test_authenticate_returns_auth_context_when_user_set(self) -> None:
        """Should return AuthContext when request.auth.user is populated."""
        bearer_auth = BearerAuth()
        request = MockRequest()
        auth_context = AuthContext(user=MagicMock(spec=User))
        request.auth = auth_context

        result = bearer_auth.authenticate(request, "test-token-123")

        assert result is auth_context

    def test_authenticate_returns_none_when_auth_missing(self) -> None:
        """Should return None when request has no auth attribute."""
        auth = BearerAuth()
        request = MockRequest()
        # No auth attribute

        result = auth.authenticate(request, "test-token-123")

        assert result is None

    def test_authenticate_returns_none_when_auth_user_is_none(self) -> None:
        """Should return None when request.auth.user is None."""
        auth = BearerAuth()
        request = MockRequest()
        request.auth = AuthContext(user=None)

        result = auth.authenticate(request, "test-token-123")

        assert result is None


@pytest.mark.django_db
class TestRequireAdmin:
    """Tests for require_admin decorator."""

    def test_allows_admin_user(self, request_factory) -> None:
        """Should allow admin users through."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org, role="admin")

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        @require_admin
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        result = view(request)
        assert result.status_code == 200

    def test_rejects_unauthenticated_user(self, request_factory) -> None:
        """Should reject unauthenticated users with 401."""
        request = request_factory.get("/")
        request = make_request_with_auth(request, AuthContext())  # No user/member/org

        @require_admin
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        with pytest.raises(HttpError) as exc:
            view(request)

        assert exc.value.status_code == 401

    def test_rejects_non_admin_user(self, request_factory) -> None:
        """Should reject non-admin users with 403."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org, role="member")

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

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

        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        result_user, result_member, result_org = get_auth_context(request)

        assert result_user == user
        assert result_member == member
        assert result_org == org

    def test_raises_401_when_not_authenticated(self, request_factory) -> None:
        """Should raise 401 when not authenticated."""
        from apps.core.security import get_auth_context

        request = request_factory.get("/")
        request = make_request_with_auth(request, AuthContext())  # No user

        with pytest.raises(HttpError) as exc:
            get_auth_context(request)

        assert exc.value.status_code == 401


@pytest.mark.django_db
class TestRequireSubscription:
    """Tests for require_subscription decorator."""

    @override_settings(SUBSCRIPTION_GATING_ENABLED=True)
    def test_allows_user_with_active_subscription(self, request_factory) -> None:
        """Should allow users with active subscription through."""
        sub = SubscriptionFactory.create(status=Subscription.Status.ACTIVE)
        org = sub.organization
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        @require_subscription
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        result = view(request)
        assert result.status_code == 200

    @override_settings(SUBSCRIPTION_GATING_ENABLED=True)
    def test_allows_user_with_trialing_subscription(self, request_factory) -> None:
        """Should allow users with trialing subscription through."""
        sub = SubscriptionFactory.create(status=Subscription.Status.TRIALING)
        org = sub.organization
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        @require_subscription
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        result = view(request)
        assert result.status_code == 200

    @override_settings(SUBSCRIPTION_GATING_ENABLED=True)
    def test_rejects_user_with_canceled_subscription(self, request_factory) -> None:
        """Should reject users with canceled subscription with 402."""
        sub = SubscriptionFactory.create(status=Subscription.Status.CANCELED)
        org = sub.organization
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        @require_subscription
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        with pytest.raises(HttpError) as exc:
            view(request)

        assert exc.value.status_code == 402

    @override_settings(SUBSCRIPTION_GATING_ENABLED=True)
    def test_rejects_user_with_no_subscription(self, request_factory) -> None:
        """Should reject users with no subscription record with 402."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        @require_subscription
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        with pytest.raises(HttpError) as exc:
            view(request)

        assert exc.value.status_code == 402

    @override_settings(SUBSCRIPTION_GATING_ENABLED=True)
    def test_rejects_unauthenticated_user(self, request_factory) -> None:
        """Should reject unauthenticated users with 401."""
        request = request_factory.get("/")
        request = make_request_with_auth(request, AuthContext())

        @require_subscription
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        with pytest.raises(HttpError) as exc:
            view(request)

        assert exc.value.status_code == 401

    @override_settings(SUBSCRIPTION_GATING_ENABLED=False)
    def test_bypasses_check_when_gating_disabled(self, request_factory) -> None:
        """Should bypass subscription check when gating is disabled."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        @require_subscription
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        result = view(request)
        assert result.status_code == 200

    @override_settings(SUBSCRIPTION_GATING_ENABLED=True)
    def test_admin_check_runs_before_subscription_check(self, request_factory) -> None:
        """Non-admin should get 403, not 402, when decorators are stacked."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org, role="member")

        request = request_factory.get("/")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        @require_admin
        @require_subscription
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("OK")

        with pytest.raises(HttpError) as exc:
            view(request)

        assert exc.value.status_code == 403
