"""
Tests for mobile user provisioning feature.

Covers the /auth/mobile/provision endpoint and provision_mobile_user service.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory, override_settings
from ninja.errors import HttpError

from apps.accounts.api import provision_mobile_user_endpoint
from apps.accounts.schemas import MobileProvisionRequest
from apps.accounts.services import provision_mobile_user
from apps.organizations.models import Organization

from .factories import MemberFactory, OrganizationFactory, UserFactory


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
    status: str = "active"


@dataclass
class MockStytchOrg:
    """Mock Stytch organization object."""

    organization_id: str
    organization_name: str
    organization_slug: str


@dataclass
class MockOrgCreateResponse:
    """Mock response for org creation."""

    organization: MockStytchOrg


@dataclass
class MockOrgGetResponse:
    """Mock response for org get."""

    organization: MockStytchOrg


@dataclass
class MockMemberCreateResponse:
    """Mock response for member creation."""

    member: MockStytchMember


@dataclass
class MockMemberGetResponse:
    """Mock response for member get."""

    member: MockStytchMember


@dataclass
class MockMemberSearchResponse:
    """Mock response for member search."""

    members: list[MockStytchMember]


@dataclass
class MockSessionAttestResponse:
    """Mock response for session attestation."""

    session_token: str
    session_jwt: str


# --- API Endpoint Tests ---


@pytest.mark.django_db
class TestMobileProvisionEndpointAuth:
    """Tests for mobile provision endpoint API key authentication."""

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_missing_api_key_returns_401(self, request_factory: RequestFactory) -> None:
        """Should return 401 when X-Mobile-API-Key header is missing."""
        request = request_factory.post("/api/v1/auth/mobile/provision")
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_name="Test Org",
            organization_slug="test-org",
        )

        with pytest.raises(HttpError) as exc_info:
            provision_mobile_user_endpoint(request, payload)

        assert exc_info.value.status_code == 401
        assert "Invalid or missing API key" in str(exc_info.value.message)

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_invalid_api_key_returns_401(self, request_factory: RequestFactory) -> None:
        """Should return 401 when API key is invalid."""
        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="wrong-key",
        )
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_name="Test Org",
            organization_slug="test-org",
        )

        with pytest.raises(HttpError) as exc_info:
            provision_mobile_user_endpoint(request, payload)

        assert exc_info.value.status_code == 401

    @override_settings(MOBILE_PROVISION_API_KEY="")
    def test_unconfigured_api_key_returns_401(self, request_factory: RequestFactory) -> None:
        """Should return 401 when MOBILE_PROVISION_API_KEY is not configured."""
        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="any-key",
        )
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_name="Test Org",
            organization_slug="test-org",
        )

        with pytest.raises(HttpError) as exc_info:
            provision_mobile_user_endpoint(request, payload)

        assert exc_info.value.status_code == 401
        assert "not configured" in str(exc_info.value.message)


@pytest.mark.django_db
class TestMobileProvisionEndpointValidation:
    """Tests for mobile provision endpoint input validation."""

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_missing_org_params_returns_400(self, request_factory: RequestFactory) -> None:
        """Should return 400 when neither organization_id nor org name/slug provided."""
        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="test-api-key",
        )
        payload = MobileProvisionRequest(email="test@example.com")

        with pytest.raises(HttpError) as exc_info:
            provision_mobile_user_endpoint(request, payload)

        assert exc_info.value.status_code == 400
        assert "Must specify either" in str(exc_info.value.message)

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_both_org_params_returns_400(self, request_factory: RequestFactory) -> None:
        """Should return 400 when both organization_id and org name/slug provided."""
        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="test-api-key",
        )
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_id="org-123",
            organization_name="Test Org",
            organization_slug="test-org",
        )

        with pytest.raises(HttpError) as exc_info:
            provision_mobile_user_endpoint(request, payload)

        assert exc_info.value.status_code == 400
        assert "Cannot specify both" in str(exc_info.value.message)

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_missing_slug_returns_400(self, request_factory: RequestFactory) -> None:
        """Should return 400 when organization_name provided without slug."""
        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="test-api-key",
        )
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_name="Test Org",
        )

        with pytest.raises(HttpError) as exc_info:
            provision_mobile_user_endpoint(request, payload)

        assert exc_info.value.status_code == 400
        assert "organization_slug" in str(exc_info.value.message).lower()


@pytest.mark.django_db
class TestMobileProvisionEndpointCreateOrg:
    """Tests for mobile provision endpoint - create organization flow."""

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_success_creates_org_and_returns_session(
        self, request_factory: RequestFactory
    ) -> None:
        """Should create org, member, user and return session tokens."""
        mock_stytch = MagicMock()

        # Mock org creation
        mock_stytch.organizations.create.return_value = MockOrgCreateResponse(
            organization=MockStytchOrg(
                organization_id="org-new-123",
                organization_name="New Corp",
                organization_slug="new-corp",
            )
        )

        # Mock member creation
        mock_stytch.organizations.members.create.return_value = MockMemberCreateResponse(
            member=MockStytchMember(
                member_id="member-new-456",
                email_address="founder@newcorp.com",
                name="Founder",
                roles=[],
            )
        )

        # Mock session attestation
        mock_stytch.sessions.attest.return_value = MockSessionAttestResponse(
            session_token="session_token_abc",
            session_jwt="jwt_xyz",
        )

        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="test-api-key",
        )
        payload = MobileProvisionRequest(
            email="founder@newcorp.com",
            name="Founder",
            organization_name="New Corp",
            organization_slug="new-corp",
        )

        with (
            patch("apps.accounts.stytch_client.get_stytch_client", return_value=mock_stytch),
            patch("apps.passkeys.trusted_auth.settings") as mock_settings,
        ):
            mock_settings.PASSKEY_JWT_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MbU+BPQE5XwVv8wI
fake_key_for_testing_only
-----END RSA PRIVATE KEY-----"""
            mock_settings.STYTCH_TRUSTED_AUTH_ISSUER = "test-issuer"
            mock_settings.STYTCH_TRUSTED_AUTH_AUDIENCE = "test-audience"
            mock_settings.STYTCH_TRUSTED_AUTH_PROFILE_ID = "test-profile-id"

            # Mock the trusted auth token creation
            with patch(
                "apps.passkeys.trusted_auth.create_trusted_auth_token",
                return_value="mock_trusted_token",
            ):
                result = provision_mobile_user_endpoint(request, payload)

        assert result.session_token == "session_token_abc"
        assert result.session_jwt == "jwt_xyz"
        assert result.member_id == "member-new-456"
        assert result.organization_id == "org-new-123"

        # Verify Stytch calls
        mock_stytch.organizations.create.assert_called_once_with(
            organization_name="New Corp",
            organization_slug="new-corp",
        )
        mock_stytch.organizations.members.create.assert_called_once()

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_slug_conflict_returns_409(self, request_factory: RequestFactory) -> None:
        """Should return 409 when organization slug already exists."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        mock_stytch = MagicMock()
        details = StytchErrorDetails(
            error_type="duplicate_slug",
            error_message="Organization slug already exists",
            error_url="https://stytch.com/docs",
            status_code=409,
            request_id="req-conflict",
        )
        mock_stytch.organizations.create.side_effect = StytchError(details)

        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="test-api-key",
        )
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_name="Existing Corp",
            organization_slug="existing-slug",
        )

        with (
            patch("apps.accounts.stytch_client.get_stytch_client", return_value=mock_stytch),
            pytest.raises(HttpError) as exc_info,
        ):
            provision_mobile_user_endpoint(request, payload)

        assert exc_info.value.status_code == 409
        assert "slug already in use" in str(exc_info.value.message).lower()


@pytest.mark.django_db
class TestMobileProvisionEndpointJoinOrg:
    """Tests for mobile provision endpoint - join existing organization flow."""

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_success_joins_org_and_returns_session(
        self, request_factory: RequestFactory
    ) -> None:
        """Should create member in existing org and return session tokens."""
        mock_stytch = MagicMock()

        # Mock org get
        mock_stytch.organizations.get.return_value = MockOrgGetResponse(
            organization=MockStytchOrg(
                organization_id="org-existing-123",
                organization_name="Existing Corp",
                organization_slug="existing-corp",
            )
        )

        # Mock member search (no existing member)
        mock_stytch.organizations.members.search.return_value = MockMemberSearchResponse(
            members=[]
        )

        # Mock member creation
        mock_stytch.organizations.members.create.return_value = MockMemberCreateResponse(
            member=MockStytchMember(
                member_id="member-new-789",
                email_address="newuser@example.com",
                name="New User",
                roles=[],
            )
        )

        # Mock session attestation
        mock_stytch.sessions.attest.return_value = MockSessionAttestResponse(
            session_token="session_token_join",
            session_jwt="jwt_join",
        )

        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="test-api-key",
        )
        payload = MobileProvisionRequest(
            email="newuser@example.com",
            name="New User",
            organization_id="org-existing-123",
        )

        with (
            patch("apps.accounts.stytch_client.get_stytch_client", return_value=mock_stytch),
            patch(
                "apps.passkeys.trusted_auth.create_trusted_auth_token",
                return_value="mock_trusted_token",
            ),
        ):
            result = provision_mobile_user_endpoint(request, payload)

        assert result.session_token == "session_token_join"
        assert result.session_jwt == "jwt_join"
        assert result.member_id == "member-new-789"
        assert result.organization_id == "org-existing-123"

    @override_settings(MOBILE_PROVISION_API_KEY="test-api-key")
    def test_reactivates_deleted_member(self, request_factory: RequestFactory) -> None:
        """Should reactivate a previously deleted member."""
        mock_stytch = MagicMock()

        # Mock org get
        mock_stytch.organizations.get.return_value = MockOrgGetResponse(
            organization=MockStytchOrg(
                organization_id="org-123",
                organization_name="Test Org",
                organization_slug="test-org",
            )
        )

        # Mock member search (returns deleted member)
        deleted_member = MockStytchMember(
            member_id="member-deleted-123",
            email_address="deleted@example.com",
            name="Deleted User",
            roles=[],
            status="deleted",
        )
        mock_stytch.organizations.members.search.return_value = MockMemberSearchResponse(
            members=[deleted_member]
        )

        # Mock member get after reactivation
        mock_stytch.organizations.members.get.return_value = MockMemberGetResponse(
            member=MockStytchMember(
                member_id="member-deleted-123",
                email_address="deleted@example.com",
                name="Deleted User",
                roles=[],
                status="active",
            )
        )

        # Mock session attestation
        mock_stytch.sessions.attest.return_value = MockSessionAttestResponse(
            session_token="session_reactivated",
            session_jwt="jwt_reactivated",
        )

        request = request_factory.post(
            "/api/v1/auth/mobile/provision",
            HTTP_X_MOBILE_API_KEY="test-api-key",
        )
        payload = MobileProvisionRequest(
            email="deleted@example.com",
            organization_id="org-123",
        )

        with (
            patch("apps.accounts.stytch_client.get_stytch_client", return_value=mock_stytch),
            patch(
                "apps.passkeys.trusted_auth.create_trusted_auth_token",
                return_value="mock_trusted_token",
            ),
        ):
            result = provision_mobile_user_endpoint(request, payload)

        # Verify reactivation was called
        mock_stytch.organizations.members.reactivate.assert_called_once_with(
            organization_id="org-123",
            member_id="member-deleted-123",
        )
        assert result.session_token == "session_reactivated"


# --- Service Tests ---


@pytest.mark.django_db
class TestProvisionMobileUserService:
    """Tests for provision_mobile_user service function."""

    def test_validates_no_org_params(self) -> None:
        """Should raise ValueError when no org params provided."""
        with pytest.raises(ValueError) as exc_info:
            provision_mobile_user(email="test@example.com")

        assert "Must specify either" in str(exc_info.value)

    def test_validates_conflicting_org_params(self) -> None:
        """Should raise ValueError when both org_id and org creation params provided."""
        with pytest.raises(ValueError) as exc_info:
            provision_mobile_user(
                email="test@example.com",
                organization_id="org-123",
                organization_name="Test",
                organization_slug="test",
            )

        assert "Cannot specify both" in str(exc_info.value)

    def test_validates_incomplete_org_creation_params(self) -> None:
        """Should raise ValueError when org_name provided without slug."""
        with pytest.raises(ValueError) as exc_info:
            provision_mobile_user(
                email="test@example.com",
                organization_name="Test Org",
            )

        assert "organization_slug" in str(exc_info.value).lower()

    def test_normalizes_email_to_lowercase(self) -> None:
        """Should normalize email to lowercase before processing."""
        mock_stytch = MagicMock()
        mock_stytch.organizations.create.return_value = MockOrgCreateResponse(
            organization=MockStytchOrg(
                organization_id="org-123",
                organization_name="Test",
                organization_slug="test",
            )
        )
        mock_stytch.organizations.members.create.return_value = MockMemberCreateResponse(
            member=MockStytchMember(
                member_id="member-123",
                email_address="user@example.com",
                name=None,
                roles=[],
            )
        )
        mock_stytch.sessions.attest.return_value = MockSessionAttestResponse(
            session_token="token",
            session_jwt="jwt",
        )

        with (
            patch("apps.accounts.stytch_client.get_stytch_client", return_value=mock_stytch),
            patch(
                "apps.passkeys.trusted_auth.create_trusted_auth_token",
                return_value="mock_token",
            ),
        ):
            user, _member, _org, _token, _jwt = provision_mobile_user(
                email="  USER@EXAMPLE.COM  ",  # Uppercase with whitespace
                organization_name="Test",
                organization_slug="test",
            )

        assert user.email == "user@example.com"

    def test_stores_phone_number_unverified(self) -> None:
        """Should store phone number with phone_verified_at=None."""
        mock_stytch = MagicMock()
        mock_stytch.organizations.create.return_value = MockOrgCreateResponse(
            organization=MockStytchOrg(
                organization_id="org-123",
                organization_name="Test",
                organization_slug="test",
            )
        )
        mock_stytch.organizations.members.create.return_value = MockMemberCreateResponse(
            member=MockStytchMember(
                member_id="member-123",
                email_address="user@example.com",
                name=None,
                roles=[],
            )
        )
        mock_stytch.sessions.attest.return_value = MockSessionAttestResponse(
            session_token="token",
            session_jwt="jwt",
        )

        with (
            patch("apps.accounts.stytch_client.get_stytch_client", return_value=mock_stytch),
            patch(
                "apps.passkeys.trusted_auth.create_trusted_auth_token",
                return_value="mock_token",
            ),
        ):
            user, _member, _org, _token, _jwt = provision_mobile_user(
                email="user@example.com",
                phone_number="+14155551234",
                organization_name="Test",
                organization_slug="test",
            )

        assert user.phone_number == "+14155551234"
        assert user.phone_verified_at is None

    def test_creator_gets_admin_role(self) -> None:
        """When creating org, creator should be made admin."""
        mock_stytch = MagicMock()
        mock_stytch.organizations.create.return_value = MockOrgCreateResponse(
            organization=MockStytchOrg(
                organization_id="org-123",
                organization_name="Test",
                organization_slug="test",
            )
        )
        mock_stytch.organizations.members.create.return_value = MockMemberCreateResponse(
            member=MockStytchMember(
                member_id="member-123",
                email_address="founder@example.com",
                name="Founder",
                roles=[],
            )
        )
        mock_stytch.sessions.attest.return_value = MockSessionAttestResponse(
            session_token="token",
            session_jwt="jwt",
        )

        with (
            patch("apps.accounts.stytch_client.get_stytch_client", return_value=mock_stytch),
            patch(
                "apps.passkeys.trusted_auth.create_trusted_auth_token",
                return_value="mock_token",
            ),
        ):
            provision_mobile_user(
                email="founder@example.com",
                name="Founder",
                organization_name="Test Corp",
                organization_slug="test-corp",
            )

        # Verify admin role was set
        mock_stytch.organizations.members.update.assert_called_once()
        call_kwargs = mock_stytch.organizations.members.update.call_args[1]
        assert "stytch_admin" in call_kwargs["roles"]

    def test_syncs_to_local_database(self) -> None:
        """Should create local User, Member, and Organization records."""
        mock_stytch = MagicMock()
        mock_stytch.organizations.get.return_value = MockOrgGetResponse(
            organization=MockStytchOrg(
                organization_id="org-local-123",
                organization_name="Local Test",
                organization_slug="local-test",
            )
        )
        mock_stytch.organizations.members.search.return_value = MockMemberSearchResponse(
            members=[]
        )
        mock_stytch.organizations.members.create.return_value = MockMemberCreateResponse(
            member=MockStytchMember(
                member_id="member-local-456",
                email_address="local@example.com",
                name="Local User",
                roles=[],
            )
        )
        mock_stytch.sessions.attest.return_value = MockSessionAttestResponse(
            session_token="token",
            session_jwt="jwt",
        )

        with (
            patch("apps.accounts.stytch_client.get_stytch_client", return_value=mock_stytch),
            patch(
                "apps.passkeys.trusted_auth.create_trusted_auth_token",
                return_value="mock_token",
            ),
        ):
            user, member, org, _token, _jwt = provision_mobile_user(
                email="local@example.com",
                name="Local User",
                organization_id="org-local-123",
            )

        # Verify local records created
        assert user.email == "local@example.com"
        assert user.name == "Local User"
        assert member.stytch_member_id == "member-local-456"
        assert member.user == user
        assert member.organization == org
        assert org.stytch_org_id == "org-local-123"
        assert org.name == "Local Test"

        # Verify records are in database
        from apps.accounts.models import Member, User

        assert User.objects.filter(email="local@example.com").exists()
        assert Member.objects.filter(stytch_member_id="member-local-456").exists()
        assert Organization.objects.filter(stytch_org_id="org-local-123").exists()


# --- Schema Tests ---


class TestMobileProvisionRequestSchema:
    """Tests for MobileProvisionRequest schema validation."""

    def test_valid_create_org_request(self) -> None:
        """Should accept valid org creation request."""
        payload = MobileProvisionRequest(
            email="test@example.com",
            name="Test User",
            organization_name="Test Org",
            organization_slug="test-org",
        )
        assert payload.email == "test@example.com"
        assert payload.organization_name == "Test Org"
        assert payload.organization_slug == "test-org"

    def test_valid_join_org_request(self) -> None:
        """Should accept valid join org request."""
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_id="org-123",
        )
        assert payload.email == "test@example.com"
        assert payload.organization_id == "org-123"

    def test_normalizes_slug_to_lowercase(self) -> None:
        """Should normalize organization slug to lowercase."""
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_name="Test",
            organization_slug="TEST-ORG",
        )
        assert payload.organization_slug == "test-org"

    def test_normalizes_slug_with_spaces(self) -> None:
        """Should replace spaces in slug with hyphens."""
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_name="Test",
            organization_slug="test org slug",
        )
        assert payload.organization_slug == "test-org-slug"

    def test_invalid_email_rejected(self) -> None:
        """Should reject invalid email format."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MobileProvisionRequest(
                email="not-an-email",
                organization_name="Test",
                organization_slug="test",
            )

    def test_optional_fields_default_to_empty(self) -> None:
        """Optional fields should have sensible defaults."""
        payload = MobileProvisionRequest(
            email="test@example.com",
            organization_id="org-123",
        )
        assert payload.name == ""
        assert payload.phone_number == ""
