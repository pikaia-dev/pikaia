"""
Tests for core middleware.

Tests:
- CorrelationIdMiddleware: correlation ID, IP/user-agent capture
- StytchAuthMiddleware: JWT authentication, JIT sync, idempotency, error paths
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
import structlog
from django.http import HttpRequest, HttpResponse
from stytch.core.response_base import StytchError, StytchErrorDetails

from apps.accounts.models import Member, User
from apps.core.middleware import (
    CorrelationIdMiddleware,
    StytchAuthMiddleware,
    get_client_ip,
)
from apps.organizations.models import Organization


# Mock Stytch response classes
@dataclass
class MockMemberSession:
    member_id: str


@dataclass
class MockStytchMember:
    member_id: str
    email_address: str
    name: str | None
    roles: list[str]


@dataclass
class MockStytchOrg:
    organization_id: str
    organization_name: str
    organization_slug: str


@dataclass
class MockJWTAuthResponse:
    """Mock for sessions.authenticate_jwt response (local JWT verification)."""

    member: MockStytchMember
    member_session: MockMemberSession


@dataclass
class MockFullAuthResponse:
    """Mock for sessions.authenticate response (full API call)."""

    member: MockStytchMember
    organization: MockStytchOrg


class TestGetClientIp:
    """Tests for get_client_ip helper function."""

    def test_extracts_ip_from_remote_addr(self):
        """Should extract IP from REMOTE_ADDR when no X-Forwarded-For."""
        request = HttpRequest()
        request.META = {"REMOTE_ADDR": "192.168.1.1"}

        assert get_client_ip(request) == "192.168.1.1"

    def test_extracts_first_ip_from_x_forwarded_for(self):
        """Should extract first IP from X-Forwarded-For (original client)."""
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.1, 10.0.0.1, 10.0.0.2",
            "REMOTE_ADDR": "127.0.0.1",
        }

        assert get_client_ip(request) == "203.0.113.1"

    def test_handles_single_x_forwarded_for(self):
        """Should handle single IP in X-Forwarded-For."""
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.1",
            "REMOTE_ADDR": "127.0.0.1",
        }

        assert get_client_ip(request) == "203.0.113.1"

    def test_strips_whitespace_from_x_forwarded_for(self):
        """Should strip whitespace from IP addresses."""
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "  203.0.113.1  ,  10.0.0.1  ",
            "REMOTE_ADDR": "127.0.0.1",
        }

        assert get_client_ip(request) == "203.0.113.1"

    def test_returns_none_when_no_ip(self):
        """Should return None when no IP available."""
        request = HttpRequest()
        request.META = {}

        assert get_client_ip(request) is None


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware IP and user-agent capture."""

    def test_binds_ip_address_to_contextvars(self):
        """Should bind IP address to structlog contextvars."""

        def get_response(request):
            # Check context inside request
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request.ip_address") == "203.0.113.1"
            return HttpResponse()

        middleware = CorrelationIdMiddleware(get_response)

        request = HttpRequest()
        request.path = "/api/v1/test"
        request.method = "GET"
        request.META = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.1",
            "REMOTE_ADDR": "127.0.0.1",
        }

        middleware(request)

    def test_binds_user_agent_to_contextvars(self):
        """Should bind user-agent to structlog contextvars."""

        def get_response(request):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request.user_agent") == "Mozilla/5.0 Test"
            return HttpResponse()

        middleware = CorrelationIdMiddleware(get_response)

        request = HttpRequest()
        request.path = "/api/v1/test"
        request.method = "GET"
        request.META = {
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_USER_AGENT": "Mozilla/5.0 Test",
        }

        middleware(request)

    def test_truncates_long_user_agent(self):
        """Should truncate user-agent to MAX_USER_AGENT_LENGTH."""
        long_user_agent = "A" * 1000

        def get_response(request):
            ctx = structlog.contextvars.get_contextvars()
            user_agent = ctx.get("request.user_agent", "")
            assert len(user_agent) == 512  # MAX_USER_AGENT_LENGTH
            assert user_agent == "A" * 512
            return HttpResponse()

        middleware = CorrelationIdMiddleware(get_response)

        request = HttpRequest()
        request.path = "/api/v1/test"
        request.method = "GET"
        request.META = {
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_USER_AGENT": long_user_agent,
        }

        middleware(request)

    def test_handles_missing_user_agent(self):
        """Should handle missing user-agent gracefully."""

        def get_response(request):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request.user_agent") == ""
            return HttpResponse()

        middleware = CorrelationIdMiddleware(get_response)

        request = HttpRequest()
        request.path = "/api/v1/test"
        request.method = "GET"
        request.META = {"REMOTE_ADDR": "127.0.0.1"}

        middleware(request)


def make_request(path: str = "/api/v1/test", auth_header: str | None = None) -> HttpRequest:
    """Create a mock HttpRequest."""
    request = HttpRequest()
    request.path = path
    request.method = "GET"
    request.META = {}
    if auth_header:
        request.META["HTTP_AUTHORIZATION"] = auth_header
    return request


def make_get_response() -> MagicMock:
    """Create a mock get_response callable."""
    return MagicMock(return_value=HttpResponse())


@pytest.fixture
def middleware():
    """Create middleware instance."""
    return StytchAuthMiddleware(make_get_response())


@pytest.mark.django_db
class TestPublicPaths:
    """Tests for public path handling."""

    def test_public_path_skips_auth(self, middleware: StytchAuthMiddleware) -> None:
        """Public paths should not attempt JWT authentication."""
        request = make_request("/api/v1/health")

        with patch.object(middleware, "_authenticate_jwt") as mock_auth:
            middleware(request)
            mock_auth.assert_not_called()

    def test_admin_path_is_public(self, middleware: StytchAuthMiddleware) -> None:
        """Admin paths should be public."""
        request = make_request("/admin/login/")

        with patch.object(middleware, "_authenticate_jwt") as mock_auth:
            middleware(request)
            mock_auth.assert_not_called()

    def test_non_public_path_attempts_auth(self, middleware: StytchAuthMiddleware) -> None:
        """Non-public paths with Bearer token should attempt auth."""
        request = make_request("/api/v1/protected", "Bearer test-jwt")

        with patch.object(middleware, "_authenticate_jwt") as mock_auth:
            middleware(request)
            mock_auth.assert_called_once_with(request, "test-jwt")


@pytest.mark.django_db
class TestJWTAuthentication:
    """Tests for JWT authentication flow."""

    def test_no_auth_header_sets_none(self, middleware: StytchAuthMiddleware) -> None:
        """Request without Authorization header gets None auth context."""
        request = make_request("/api/v1/test")
        middleware(request)

        assert request.auth_user is None
        assert request.auth_member is None
        assert request.auth_organization is None

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_valid_jwt_with_existing_member(
        self,
        mock_get_client: MagicMock,
        middleware: StytchAuthMiddleware,
    ) -> None:
        """Valid JWT with existing local member populates auth context (fast path)."""
        # Create local records
        user = User.objects.create(email="test@example.com", name="Test User")
        org = Organization.objects.create(
            stytch_org_id="org-123",
            name="Test Org",
            slug="test-org",
        )
        Member.objects.create(
            stytch_member_id="member-123",
            user=user,
            organization=org,
            role="member",
        )

        # Mock local JWT verification (no API call)
        mock_client = MagicMock()
        mock_client.sessions.authenticate_jwt.return_value = MockJWTAuthResponse(
            member=MockStytchMember(
                member_id="member-123",
                email_address="test@example.com",
                name="Test User",
                roles=[],
            ),
            member_session=MockMemberSession(member_id="member-123"),
        )
        mock_get_client.return_value = mock_client

        # Make request
        request = make_request("/api/v1/test", "Bearer valid-jwt")
        middleware(request)

        # Fast path: should use local DB, NOT call sessions.authenticate
        mock_client.sessions.authenticate.assert_not_called()
        assert request.auth_user.email == "test@example.com"
        assert request.auth_member.stytch_member_id == "member-123"
        assert request.auth_organization.stytch_org_id == "org-123"

    @patch("apps.core.middleware.bind_contextvars")
    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_valid_jwt_binds_user_context_for_logging(
        self,
        mock_get_client: MagicMock,
        mock_bind_contextvars: MagicMock,
        middleware: StytchAuthMiddleware,
    ) -> None:
        """Valid JWT should bind user/org context for structured logging."""
        # Create local records
        user = User.objects.create(email="context@example.com", name="Context User")
        org = Organization.objects.create(
            stytch_org_id="org-context-123",
            name="Context Org",
            slug="context-org",
        )
        Member.objects.create(
            stytch_member_id="member-context-123",
            user=user,
            organization=org,
            role="member",
        )

        # Mock local JWT verification
        mock_client = MagicMock()
        mock_client.sessions.authenticate_jwt.return_value = MockJWTAuthResponse(
            member=MockStytchMember(
                member_id="member-context-123",
                email_address="context@example.com",
                name="Context User",
                roles=[],
            ),
            member_session=MockMemberSession(member_id="member-context-123"),
        )
        mock_get_client.return_value = mock_client

        # Make request
        request = make_request("/api/v1/test", "Bearer valid-jwt")
        middleware(request)

        # Verify bind_contextvars was called with user/org context
        mock_bind_contextvars.assert_called()
        call_kwargs = mock_bind_contextvars.call_args[1]
        assert call_kwargs.get("usr.id") == str(user.id)
        assert call_kwargs.get("usr.email") == "context@example.com"
        assert call_kwargs.get("organization.id") == "org-context-123"

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_invalid_jwt_sets_none(
        self,
        mock_get_client: MagicMock,
        middleware: StytchAuthMiddleware,
    ) -> None:
        """Invalid/expired JWT results in None auth context."""
        mock_client = MagicMock()
        # Local JWT verification fails
        mock_client.sessions.authenticate_jwt.side_effect = StytchError(
            StytchErrorDetails(
                status_code=401,
                request_id="test-request-id",
                error_type="invalid_jwt",
                error_message="JWT is invalid",
            )
        )
        mock_get_client.return_value = mock_client

        request = make_request("/api/v1/test", "Bearer invalid-jwt")
        middleware(request)

        assert request.auth_user is None
        assert request.auth_member is None
        assert request.auth_organization is None


@pytest.mark.django_db
class TestJITSync:
    """Tests for Just-In-Time member sync."""

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_jit_sync_creates_local_records(
        self,
        mock_get_client: MagicMock,
        middleware: StytchAuthMiddleware,
    ) -> None:
        """JIT sync creates User, Member, Organization when not in local DB."""
        # Mock JWT validation succeeds with member data
        mock_client = MagicMock()
        mock_client.sessions.authenticate_jwt.return_value = MockJWTAuthResponse(
            member=MockStytchMember(
                member_id="member-new-456",
                email_address="new@example.com",
                name="New User",
                roles=[],
            ),
            member_session=MockMemberSession(member_id="member-new-456"),
        )

        # Mock full authenticate for JIT sync (called when member not in local DB)
        mock_client.sessions.authenticate.return_value = MockFullAuthResponse(
            member=MockStytchMember(
                member_id="member-new-456",
                email_address="new@example.com",
                name="New User",
                roles=[],
            ),
            organization=MockStytchOrg(
                organization_id="org-new-789",
                organization_name="New Org",
                organization_slug="new-org",
            ),
        )
        mock_get_client.return_value = mock_client

        # No local records exist
        assert not Member.objects.filter(stytch_member_id="member-new-456").exists()

        request = make_request("/api/v1/test", "Bearer valid-jwt")
        middleware(request)

        # Slow path: should call full authenticate since member not in DB
        mock_client.sessions.authenticate.assert_called_once()

        # Records should be created
        assert request.auth_user is not None
        assert request.auth_user.email == "new@example.com"
        assert request.auth_member is not None
        assert request.auth_member.stytch_member_id == "member-new-456"
        assert request.auth_organization is not None
        assert request.auth_organization.stytch_org_id == "org-new-789"

        # Verify DB records
        assert Member.objects.filter(stytch_member_id="member-new-456").exists()
        assert User.objects.filter(email="new@example.com").exists()
        assert Organization.objects.filter(stytch_org_id="org-new-789").exists()

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_jit_sync_is_idempotent(
        self,
        mock_get_client: MagicMock,
        middleware: StytchAuthMiddleware,
    ) -> None:
        """First request syncs from Stytch, second uses local DB (fast path)."""
        mock_client = MagicMock()
        mock_client.sessions.authenticate_jwt.return_value = MockJWTAuthResponse(
            member=MockStytchMember(
                member_id="member-idempotent-123",
                email_address="idempotent@example.com",
                name="Idempotent User",
                roles=[],
            ),
            member_session=MockMemberSession(member_id="member-idempotent-123"),
        )
        mock_client.sessions.authenticate.return_value = MockFullAuthResponse(
            member=MockStytchMember(
                member_id="member-idempotent-123",
                email_address="idempotent@example.com",
                name="Idempotent User",
                roles=[],
            ),
            organization=MockStytchOrg(
                organization_id="org-idempotent-456",
                organization_name="Idempotent Org",
                organization_slug="idempotent-org",
            ),
        )
        mock_get_client.return_value = mock_client

        # First request - creates records (slow path)
        request1 = make_request("/api/v1/test", "Bearer jwt1")
        middleware(request1)

        # Second request - should use local DB (fast path)
        request2 = make_request("/api/v1/test", "Bearer jwt2")
        middleware(request2)

        # Only one of each record should exist
        assert User.objects.filter(email="idempotent@example.com").count() == 1
        assert Member.objects.filter(stytch_member_id="member-idempotent-123").count() == 1
        assert Organization.objects.filter(stytch_org_id="org-idempotent-456").count() == 1

        # Full authenticate should only be called once (first request)
        assert mock_client.sessions.authenticate.call_count == 1

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_jit_sync_failure_leaves_auth_none(
        self,
        mock_get_client: MagicMock,
        middleware: StytchAuthMiddleware,
    ) -> None:
        """If JIT sync fails, auth context remains None."""
        mock_client = MagicMock()
        # JWT validates successfully locally
        mock_client.sessions.authenticate_jwt.return_value = MockJWTAuthResponse(
            member=MockStytchMember(
                member_id="member-fail-123",
                email_address="fail@example.com",
                name="Fail User",
                roles=[],
            ),
            member_session=MockMemberSession(member_id="member-fail-123"),
        )
        # But full authenticate fails (member not in local DB, so it tries to sync)
        mock_client.sessions.authenticate.side_effect = StytchError(
            StytchErrorDetails(
                status_code=401,
                request_id="test-request-id",
                error_type="session_expired",
                error_message="Session has expired",
            )
        )
        mock_get_client.return_value = mock_client

        request = make_request("/api/v1/test", "Bearer jwt")
        middleware(request)

        assert request.auth_user is None
        assert request.auth_member is None
        assert request.auth_organization is None


@pytest.mark.django_db
class TestAdminRoleSync:
    """Tests for admin role detection during JIT sync."""

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_stytch_admin_role_synced(
        self,
        mock_get_client: MagicMock,
        middleware: StytchAuthMiddleware,
    ) -> None:
        """Member with stytch_admin role gets admin role locally."""
        mock_client = MagicMock()
        mock_client.sessions.authenticate_jwt.return_value = MockJWTAuthResponse(
            member=MockStytchMember(
                member_id="member-admin-test",
                email_address="admin@example.com",
                name="Admin User",
                roles=[{"role_id": "stytch_admin"}, {"role_id": "editor"}],
            ),
            member_session=MockMemberSession(member_id="member-admin-test"),
        )
        mock_client.sessions.authenticate.return_value = MockFullAuthResponse(
            member=MockStytchMember(
                member_id="member-admin-test",
                email_address="admin@example.com",
                name="Admin User",
                roles=[{"role_id": "stytch_admin"}, {"role_id": "editor"}],
            ),
            organization=MockStytchOrg(
                organization_id="org-admin-test",
                organization_name="Admin Org",
                organization_slug="admin-org",
            ),
        )
        mock_get_client.return_value = mock_client

        request = make_request("/api/v1/test", "Bearer jwt")
        middleware(request)

        assert request.auth_member is not None
        assert request.auth_member.role == "admin"
        assert request.auth_member.is_admin is True
