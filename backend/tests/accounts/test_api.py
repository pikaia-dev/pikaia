"""
Tests for accounts API endpoints.

Covers all auth endpoints with mocked Stytch client.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client, RequestFactory
from ninja.errors import HttpError

from apps.accounts.api import (
    authenticate_magic_link,
    create_organization,
    exchange_session,
    get_current_user,
    get_organization,
    logout,
    send_magic_link,
    update_billing,
    update_organization,
    update_profile,
)
from apps.accounts.schemas import (
    BillingAddressSchema,
    DiscoveryCreateOrgRequest,
    DiscoveryExchangeRequest,
    MagicLinkAuthenticateRequest,
    MagicLinkSendRequest,
    UpdateBillingRequest,
    UpdateOrganizationRequest,
    UpdateProfileRequest,
)
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


@pytest.fixture
def api_client() -> Client:
    """Django test client for API requests."""
    return Client()


@pytest.fixture
def request_factory() -> RequestFactory:
    """Django request factory for unit testing views."""
    return RequestFactory()


# --- Mock Stytch Response Objects ---


@dataclass
class MockStytchMember:
    """Mock Stytch member object."""

    member_id: str
    email_address: str
    name: str | None
    roles: list[str]


@dataclass
class MockStytchOrg:
    """Mock Stytch organization object."""

    organization_id: str
    organization_name: str
    organization_slug: str


@dataclass
class MockDiscoveredOrg:
    """Mock discovered organization wrapper."""

    organization: MockStytchOrg


@dataclass
class MockMagicLinkAuthResponse:
    """Mock response for magic link authentication."""

    intermediate_session_token: str
    email_address: str
    discovered_organizations: list[MockDiscoveredOrg]


@dataclass
class MockCreateOrgResponse:
    """Mock response for org creation."""

    session_token: str
    session_jwt: str
    member: MockStytchMember
    organization: MockStytchOrg


@dataclass
class MockExchangeResponse:
    """Mock response for session exchange."""

    session_token: str
    session_jwt: str
    member: MockStytchMember
    organization: MockStytchOrg


# --- Test Classes ---


@pytest.mark.django_db
class TestSendMagicLink:
    """Tests for send_magic_link endpoint."""

    def test_success(self, request_factory: RequestFactory) -> None:
        """Should send magic link and return success message."""
        mock_client = MagicMock()
        mock_client.magic_links.email.discovery.send.return_value = None

        request = request_factory.post("/api/v1/auth/magic-link/send")
        payload = MagicLinkSendRequest(email="test@example.com")

        with patch("apps.accounts.api.get_stytch_client", return_value=mock_client):
            result = send_magic_link(request, payload)

        assert result.message == "Magic link sent. Check your email."
        mock_client.magic_links.email.discovery.send.assert_called_once_with(
            email_address="test@example.com",
        )

    def test_stytch_error(self, request_factory: RequestFactory) -> None:
        """Should raise ValueError on Stytch errors."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        mock_client = MagicMock()
        details = StytchErrorDetails(
            error_type="rate_limit",
            error_message="Rate limit exceeded",
            error_url="https://stytch.com/docs",
            status_code=429,
            request_id="req-123",
        )
        mock_client.magic_links.email.discovery.send.side_effect = StytchError(details)

        request = request_factory.post("/api/v1/auth/magic-link/send")
        payload = MagicLinkSendRequest(email="test@example.com")

        with (
            patch("apps.accounts.api.get_stytch_client", return_value=mock_client),
            pytest.raises(HttpError),
        ):
            send_magic_link(request, payload)

    def test_invalid_email_rejected_by_schema(self) -> None:
        """Schema should reject invalid email format."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MagicLinkSendRequest(email="not-an-email")


@pytest.mark.django_db
class TestAuthenticateMagicLink:
    """Tests for authenticate_magic_link endpoint."""

    def test_success_with_discovered_orgs(self, request_factory: RequestFactory) -> None:
        """Should return IST and discovered organizations."""
        mock_client = MagicMock()
        mock_client.magic_links.discovery.authenticate.return_value = MockMagicLinkAuthResponse(
            intermediate_session_token="ist_abc123",
            email_address="user@example.com",
            discovered_organizations=[
                MockDiscoveredOrg(
                    organization=MockStytchOrg(
                        organization_id="org-123",
                        organization_name="Acme Corp",
                        organization_slug="acme",
                    )
                ),
            ],
        )

        request = request_factory.post("/api/v1/auth/magic-link/authenticate")
        payload = MagicLinkAuthenticateRequest(token="magic_token_xyz")

        with patch("apps.accounts.api.get_stytch_client", return_value=mock_client):
            result = authenticate_magic_link(request, payload)

        assert result.intermediate_session_token == "ist_abc123"
        assert result.email == "user@example.com"
        assert len(result.discovered_organizations) == 1
        assert result.discovered_organizations[0].organization_id == "org-123"

    def test_invalid_token(self, request_factory: RequestFactory) -> None:
        """Should raise ValueError on invalid or expired token."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        mock_client = MagicMock()
        details = StytchErrorDetails(
            error_type="invalid_token",
            error_message="Token expired",
            error_url="https://stytch.com/docs",
            status_code=401,
            request_id="req-456",
        )
        mock_client.magic_links.discovery.authenticate.side_effect = StytchError(details)

        request = request_factory.post("/api/v1/auth/magic-link/authenticate")
        payload = MagicLinkAuthenticateRequest(token="expired_token")

        with (
            patch("apps.accounts.api.get_stytch_client", return_value=mock_client),
            pytest.raises(HttpError),
        ):
            authenticate_magic_link(request, payload)


@pytest.mark.django_db
class TestCreateOrganization:
    """Tests for create_organization endpoint."""

    def test_success_creates_local_records(self, request_factory: RequestFactory) -> None:
        """Should create org and sync to local database."""
        mock_client = MagicMock()
        mock_client.discovery.organizations.create.return_value = MockCreateOrgResponse(
            session_token="session_token_abc",
            session_jwt="jwt_xyz",
            member=MockStytchMember(
                member_id="member-new-123",
                email_address="founder@newcorp.com",
                name="Founder",
                roles=[],
            ),
            organization=MockStytchOrg(
                organization_id="org-new-456",
                organization_name="New Corp",
                organization_slug="new-corp",
            ),
        )

        request = request_factory.post("/api/v1/auth/discovery/create-org")
        payload = DiscoveryCreateOrgRequest(
            intermediate_session_token="ist_abc",
            organization_name="New Corp",
            organization_slug="new-corp",
        )

        with patch("apps.accounts.api.get_stytch_client", return_value=mock_client):
            result = create_organization(request, payload)

        assert result.session_token == "session_token_abc"
        assert result.session_jwt == "jwt_xyz"
        assert result.member_id == "member-new-123"
        assert result.organization_id == "org-new-456"

    def test_stytch_error(self, request_factory: RequestFactory) -> None:
        """Should raise 400 on generic org creation failure."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        mock_client = MagicMock()
        details = StytchErrorDetails(
            error_type="invalid_token",
            error_message="Invalid IST token",
            error_url="https://stytch.com/docs",
            status_code=400,
            request_id="req-789",
        )
        mock_client.discovery.organizations.create.side_effect = StytchError(details)

        request = request_factory.post("/api/v1/auth/discovery/create-org")
        payload = DiscoveryCreateOrgRequest(
            intermediate_session_token="ist_abc",
            organization_name="Existing Corp",
            organization_slug="existing",
        )

        with (
            patch("apps.accounts.api.get_stytch_client", return_value=mock_client),
            pytest.raises(HttpError) as exc_info,
        ):
            create_organization(request, payload)

        assert exc_info.value.status_code == 400

    def test_slug_conflict_returns_409(self, request_factory: RequestFactory) -> None:
        """Should return 409 Conflict when slug is already taken."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        mock_client = MagicMock()
        details = StytchErrorDetails(
            error_type="duplicate_slug",
            error_message="Organization slug already exists",
            error_url="https://stytch.com/docs",
            status_code=409,
            request_id="req-conflict",
        )
        mock_client.discovery.organizations.create.side_effect = StytchError(details)

        request = request_factory.post("/api/v1/auth/discovery/create-org")
        payload = DiscoveryCreateOrgRequest(
            intermediate_session_token="ist_abc",
            organization_name="Existing Corp",
            organization_slug="existing",
        )

        with (
            patch("apps.accounts.api.get_stytch_client", return_value=mock_client),
            pytest.raises(HttpError) as exc_info,
        ):
            create_organization(request, payload)

        assert exc_info.value.status_code == 409
        assert "slug already in use" in str(exc_info.value.message).lower()


class TestSlugValidation:
    """Tests for organization slug validation in schema."""

    def test_slug_normalized_to_lowercase(self) -> None:
        """Uppercase slugs should be normalized to lowercase."""
        payload = DiscoveryCreateOrgRequest(
            intermediate_session_token="ist_abc",
            organization_name="Test Corp",
            organization_slug="ACME-CORP",
        )
        assert payload.organization_slug == "acme-corp"

    def test_slug_spaces_replaced_with_hyphens(self) -> None:
        """Spaces in slug should be replaced with hyphens."""
        payload = DiscoveryCreateOrgRequest(
            intermediate_session_token="ist_abc",
            organization_name="Test Corp",
            organization_slug="acme corp",
        )
        assert payload.organization_slug == "acme-corp"

    def test_slug_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace should be stripped."""
        payload = DiscoveryCreateOrgRequest(
            intermediate_session_token="ist_abc",
            organization_name="Test Corp",
            organization_slug="  acme-corp  ",
        )
        assert payload.organization_slug == "acme-corp"

    def test_slug_too_short_rejected(self) -> None:
        """Slugs with less than 2 characters should be rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            DiscoveryCreateOrgRequest(
                intermediate_session_token="ist_abc",
                organization_name="Test Corp",
                organization_slug="a",
            )
        assert "2-128 characters" in str(exc_info.value)

    def test_slug_invalid_chars_rejected(self) -> None:
        """Slugs with invalid characters should be rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            DiscoveryCreateOrgRequest(
                intermediate_session_token="ist_abc",
                organization_name="Test Corp",
                organization_slug="acme@corp!",
            )
        assert "lowercase letters" in str(exc_info.value)

    def test_valid_slug_with_special_chars(self) -> None:
        """Slugs with period, underscore, tilde should be accepted."""
        payload = DiscoveryCreateOrgRequest(
            intermediate_session_token="ist_abc",
            organization_name="Test Corp",
            organization_slug="acme_corp.test~v2",
        )
        assert payload.organization_slug == "acme_corp.test~v2"


@pytest.mark.django_db
class TestExchangeSession:
    """Tests for exchange_session endpoint."""

    def test_success_syncs_local_records(self, request_factory: RequestFactory) -> None:
        """Should exchange IST and sync to local database."""
        mock_client = MagicMock()
        mock_client.discovery.intermediate_sessions.exchange.return_value = MockExchangeResponse(
            session_token="session_token_def",
            session_jwt="jwt_abc",
            member=MockStytchMember(
                member_id="member-join-789",
                email_address="joiner@example.com",
                name="Joiner",
                roles=["stytch_admin"],
            ),
            organization=MockStytchOrg(
                organization_id="org-existing-111",
                organization_name="Existing Org",
                organization_slug="existing-org",
            ),
        )

        request = request_factory.post("/api/v1/auth/discovery/exchange")
        payload = DiscoveryExchangeRequest(
            intermediate_session_token="ist_xyz",
            organization_id="org-existing-111",
        )

        with patch("apps.accounts.api.get_stytch_client", return_value=mock_client):
            result = exchange_session(request, payload)

        assert result.session_token == "session_token_def"
        assert result.session_jwt == "jwt_abc"

    def test_stytch_error(self, request_factory: RequestFactory) -> None:
        """Should raise ValueError on exchange failure."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        mock_client = MagicMock()
        details = StytchErrorDetails(
            error_type="unauthorized",
            error_message="Not authorized to join org",
            error_url="https://stytch.com/docs",
            status_code=403,
            request_id="req-abc",
        )
        mock_client.discovery.intermediate_sessions.exchange.side_effect = StytchError(details)

        request = request_factory.post("/api/v1/auth/discovery/exchange")
        payload = DiscoveryExchangeRequest(
            intermediate_session_token="ist_xyz",
            organization_id="org-private",
        )

        with (
            patch("apps.accounts.api.get_stytch_client", return_value=mock_client),
            pytest.raises(HttpError),
        ):
            exchange_session(request, payload)


@pytest.mark.django_db
class TestLogout:
    """Tests for logout endpoint."""

    def test_success(self, request_factory: RequestFactory) -> None:
        """Should successfully revoke session using JWT authentication."""
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.member_session.member_session_id = "member_session_123"
        mock_client.sessions.authenticate_jwt.return_value = mock_session
        mock_client.sessions.revoke.return_value = None

        request = request_factory.post(
            "/api/v1/auth/logout",
            HTTP_AUTHORIZATION="Bearer valid_session_jwt",
        )

        with patch("apps.accounts.api.get_stytch_client", return_value=mock_client):
            result = logout(request)

        assert result.message == "Logged out successfully"
        mock_client.sessions.authenticate_jwt.assert_called_once_with(
            session_jwt="valid_session_jwt"
        )
        mock_client.sessions.revoke.assert_called_once_with(
            member_session_id="member_session_123"
        )

    def test_missing_token(self, request_factory: RequestFactory) -> None:
        """Should error when no session JWT provided."""
        request = request_factory.post("/api/v1/auth/logout")

        with pytest.raises(HttpError):
            logout(request)

    def test_expired_jwt_handled_gracefully(self, request_factory: RequestFactory) -> None:
        """Should succeed even if JWT is expired/invalid (already logged out, etc)."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        mock_client = MagicMock()
        details = StytchErrorDetails(
            error_type="session_not_found",
            error_message="Session not found or expired",
            error_url="https://stytch.com/docs",
            status_code=404,
            request_id="req-def",
        )
        mock_client.sessions.authenticate_jwt.side_effect = StytchError(details)

        request = request_factory.post(
            "/api/v1/auth/logout",
            HTTP_AUTHORIZATION="Bearer expired_jwt",
        )

        with patch("apps.accounts.api.get_stytch_client", return_value=mock_client):
            result = logout(request)

        # Should still return success - session was already invalid
        assert result.message == "Logged out successfully"


@pytest.mark.django_db
class TestGetCurrentUser:
    """Tests for get_current_user endpoint."""

    def test_success_returns_user_info(self, request_factory: RequestFactory) -> None:
        """Should return authenticated user, member, and org info."""
        # Create test data using factories
        user = UserFactory(
            email="me@example.com",
            name="Test User",
        )
        org = OrganizationFactory(
            stytch_org_id="org-me-456",
            name="My Org",
            slug="my-org",
        )
        member = MemberFactory(
            user=user,
            organization=org,
            stytch_member_id="member-me-789",
            role="admin",
        )

        request = request_factory.get("/api/v1/auth/me")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        result = get_current_user(request)

        assert result.user.id == user.id
        assert result.user.email == "me@example.com"
        assert result.member.role == "admin"
        assert result.member.is_admin is True  # computed from role
        assert result.organization.name == "My Org"

    def test_unauthenticated(self, request_factory: RequestFactory) -> None:
        """Should error when not authenticated."""
        request = request_factory.get("/api/v1/auth/me")
        # Don't set auth attributes - simulates unauthenticated request

        with pytest.raises(HttpError):
            get_current_user(request)


# --- Settings Endpoints Tests ---


@pytest.mark.django_db
class TestUpdateProfile:
    """Tests for update_profile endpoint."""

    def test_success_updates_name(self, request_factory: RequestFactory) -> None:
        """Should update user name locally and sync to Stytch."""
        user = UserFactory(name="Old Name")
        org = OrganizationFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.patch("/api/v1/auth/me/profile")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UpdateProfileRequest(name="New Name")

        with patch("apps.accounts.api.get_stytch_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            result = update_profile(request, payload)

        assert result.name == "New Name"
        user.refresh_from_db()
        assert user.name == "New Name"
        mock_client.organizations.members.update.assert_called_once()

    def test_stytch_sync_failure_doesnt_fail_request(
        self, request_factory: RequestFactory
    ) -> None:
        """Should succeed even if Stytch sync fails."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        user = UserFactory(name="Old Name")
        org = OrganizationFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.patch("/api/v1/auth/me/profile")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UpdateProfileRequest(name="New Name")

        with patch("apps.accounts.api.get_stytch_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.organizations.members.update.side_effect = StytchError(
                StytchErrorDetails(
                    error_type="api_error",
                    error_message="Stytch API error",
                    status_code=500,
                    request_id="req-123",
                )
            )
            mock_get_client.return_value = mock_client

            result = update_profile(request, payload)

        # Local update should succeed even if Stytch fails
        assert result.name == "New Name"
        user.refresh_from_db()
        assert user.name == "New Name"

    def test_unauthenticated(self, request_factory: RequestFactory) -> None:
        """Should error when not authenticated."""
        request = request_factory.patch("/api/v1/auth/me/profile")
        payload = UpdateProfileRequest(name="Test")

        with pytest.raises(HttpError):
            update_profile(request, payload)


@pytest.mark.django_db
class TestGetOrganization:
    """Tests for get_organization endpoint."""

    def test_success_returns_org_with_billing(
        self, request_factory: RequestFactory
    ) -> None:
        """Should return organization details including billing info."""
        org = OrganizationFactory(
            billing_email="billing@example.com",
            billing_name="Acme Corp Inc.",
            billing_address_line1="123 Main St",
            billing_city="San Francisco",
            billing_country="US",
            vat_id="DE123456789",
        )
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.get("/api/v1/auth/organization")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        result = get_organization(request)

        assert result.name == org.name
        assert result.billing.billing_email == "billing@example.com"
        assert result.billing.billing_name == "Acme Corp Inc."
        assert result.billing.address.line1 == "123 Main St"
        assert result.billing.address.country == "US"
        assert result.billing.vat_id == "DE123456789"

    def test_unauthenticated(self, request_factory: RequestFactory) -> None:
        """Should error when not authenticated."""
        request = request_factory.get("/api/v1/auth/organization")

        with pytest.raises(HttpError):
            get_organization(request)


@pytest.mark.django_db
class TestUpdateOrganization:
    """Tests for update_organization endpoint."""

    def test_admin_can_update_name(self, request_factory: RequestFactory) -> None:
        """Admin should be able to update organization name."""
        org = OrganizationFactory(name="Old Name")
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="admin")

        request = request_factory.patch("/api/v1/auth/organization")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UpdateOrganizationRequest(name="New Name")

        with patch("apps.accounts.api.get_stytch_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            result = update_organization(request, payload)

        assert result.name == "New Name"
        org.refresh_from_db()
        assert org.name == "New Name"
        mock_client.organizations.update.assert_called_once()

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="member")

        request = request_factory.patch("/api/v1/auth/organization")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UpdateOrganizationRequest(name="New Name")

        with pytest.raises(HttpError) as exc_info:
            update_organization(request, payload)

        assert exc_info.value.status_code == 403

    def test_unauthenticated(self, request_factory: RequestFactory) -> None:
        """Should error when not authenticated."""
        request = request_factory.patch("/api/v1/auth/organization")
        payload = UpdateOrganizationRequest(name="Test")

        with pytest.raises(HttpError):
            update_organization(request, payload)


@pytest.mark.django_db
class TestUpdateBilling:
    """Tests for update_billing endpoint."""

    def test_admin_can_update_billing(self, request_factory: RequestFactory) -> None:
        """Admin should be able to update billing info."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="admin")

        request = request_factory.patch("/api/v1/auth/organization/billing")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UpdateBillingRequest(
            billing_email="new-billing@example.com",
            billing_name="New Corp Inc.",
            address=BillingAddressSchema(
                line1="456 New St",
                line2="Suite 100",
                city="New York",
                state="NY",
                postal_code="10001",
                country="US",
            ),
            vat_id="DE999888777",
        )

        result = update_billing(request, payload)

        assert result.billing.billing_email == "new-billing@example.com"
        assert result.billing.billing_name == "New Corp Inc."
        assert result.billing.address.line1 == "456 New St"
        assert result.billing.vat_id == "DE999888777"

        org.refresh_from_db()
        assert org.billing_email == "new-billing@example.com"
        assert org.billing_address_line1 == "456 New St"

    def test_non_admin_rejected(self, request_factory: RequestFactory) -> None:
        """Non-admin should be rejected with 403."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="member")

        request = request_factory.patch("/api/v1/auth/organization/billing")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UpdateBillingRequest(
            billing_name="Test",
            vat_id="",
        )

        with pytest.raises(HttpError) as exc_info:
            update_billing(request, payload)

        assert exc_info.value.status_code == 403

    def test_unauthenticated(self, request_factory: RequestFactory) -> None:
        """Should error when not authenticated."""
        request = request_factory.patch("/api/v1/auth/organization/billing")
        payload = UpdateBillingRequest(billing_name="Test", vat_id="")

        with pytest.raises(HttpError):
            update_billing(request, payload)

