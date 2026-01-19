"""
Tests for passkey API endpoints.

Tests registration, authentication, listing, and deletion endpoints
with mocked WebAuthn responses.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.test import RequestFactory
from ninja.errors import HttpError

from apps.core.auth import AuthContext
from apps.passkeys.api import (
    delete_passkey,
    get_authentication_options,
    get_registration_options,
    list_passkeys,
    verify_authentication,
    verify_registration,
)
from apps.passkeys.schemas import (
    PasskeyAuthenticationOptionsRequest,
    PasskeyAuthenticationVerifyRequest,
    PasskeyRegistrationVerifyRequest,
)
from tests.accounts.factories import MemberFactory, UserFactory
from tests.passkeys.factories import PasskeyFactory


@pytest.mark.django_db
class TestGetRegistrationOptions:
    """Tests for POST /passkeys/register/options endpoint."""

    def test_returns_registration_options(self, request_factory: RequestFactory):
        """Should return valid registration options for authenticated user."""
        member = MemberFactory.create()
        user = member.user

        request = request_factory.post("/api/v1/passkeys/register/options")
        request.auth = AuthContext(user=user, member=member, organization=member.organization)

        response = get_registration_options(request)

        assert response.challenge_id is not None
        assert response.options is not None
        assert "challenge" in response.options
        assert "rp" in response.options
        assert "user" in response.options

    def test_excludes_existing_passkeys(self, request_factory: RequestFactory):
        """Should exclude already registered passkeys."""
        member = MemberFactory.create()
        user = member.user
        PasskeyFactory.create(user=user, credential_id=b"existing_cred")

        request = request_factory.post("/api/v1/passkeys/register/options")
        request.auth = AuthContext(user=user, member=member, organization=member.organization)

        response = get_registration_options(request)

        # Should have exclude credentials
        assert len(response.options.get("excludeCredentials", [])) == 1


@pytest.mark.django_db
class TestVerifyRegistration:
    """Tests for POST /passkeys/register/verify endpoint."""

    def test_rejects_invalid_challenge(self, request_factory: RequestFactory):
        """Should reject expired or invalid challenge."""
        member = MemberFactory.create()
        user = member.user

        request = request_factory.post("/api/v1/passkeys/register/verify")
        request.auth = AuthContext(user=user, member=member, organization=member.organization)

        payload = PasskeyRegistrationVerifyRequest(
            challenge_id="invalid_challenge",
            credential={"id": "test", "response": {}},
            name="Test Passkey",
        )

        with pytest.raises(HttpError) as exc_info:
            verify_registration(request, payload)

        assert exc_info.value.status_code == 400
        assert "expired or invalid" in str(exc_info.value)

    def test_rejects_wrong_user_challenge(self, request_factory: RequestFactory):
        """Should reject challenge created for different user."""
        member = MemberFactory.create()
        other_member = MemberFactory.create()

        # Create challenge for member.user
        request1 = request_factory.post("/api/v1/passkeys/register/options")
        request1.auth = AuthContext(
            user=member.user, member=member, organization=member.organization
        )
        options_response = get_registration_options(request1)

        # Try to use it with other_member's user
        request2 = request_factory.post("/api/v1/passkeys/register/verify")
        request2.auth = AuthContext(
            user=other_member.user, member=other_member, organization=other_member.organization
        )

        payload = PasskeyRegistrationVerifyRequest(
            challenge_id=options_response.challenge_id,
            credential={"id": "test", "response": {}},
            name="Test Passkey",
        )

        with pytest.raises(HttpError) as exc_info:
            verify_registration(request2, payload)

        assert exc_info.value.status_code == 400
        assert "does not match" in str(exc_info.value)

    @patch("apps.passkeys.services.verify_registration_response")
    def test_successful_registration(self, mock_verify, request_factory: RequestFactory):
        """Should create passkey on successful verification."""
        from apps.passkeys.models import Passkey

        member = MemberFactory.create()
        user = member.user

        # Generate options
        request1 = request_factory.post("/api/v1/passkeys/register/options")
        request1.auth = AuthContext(user=user, member=member, organization=member.organization)
        options_response = get_registration_options(request1)

        # Mock webauthn verification
        mock_verification = MagicMock()
        mock_verification.credential_id = b"new_credential_id"
        mock_verification.credential_public_key = b"public_key_bytes"
        mock_verification.sign_count = 0
        mock_verification.aaguid = uuid4()
        mock_verification.credential_backed_up = False
        mock_verify.return_value = mock_verification

        # Verify registration
        request2 = request_factory.post("/api/v1/passkeys/register/verify")
        request2.auth = AuthContext(user=user, member=member, organization=member.organization)

        payload = PasskeyRegistrationVerifyRequest(
            challenge_id=options_response.challenge_id,
            credential={
                "id": "bmV3X2NyZWRlbnRpYWxfaWQ",
                "rawId": "bmV3X2NyZWRlbnRpYWxfaWQ",
                "response": {
                    "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
                    "attestationObject": "o2NmbXRkbm9uZQ",
                    "transports": ["internal"],
                },
                "type": "public-key",
            },
            name="My Test Passkey",
        )

        response = verify_registration(request2, payload)

        assert response.id is not None
        assert response.name == "My Test Passkey"

        # Verify passkey was created in DB
        passkey = Passkey.objects.get(id=response.id)
        assert passkey.user == user
        assert passkey.name == "My Test Passkey"


@pytest.mark.django_db
class TestGetAuthenticationOptions:
    """Tests for POST /passkeys/authenticate/options endpoint."""

    def test_returns_authentication_options(self, request_factory: RequestFactory):
        """Should return valid authentication options."""
        request = request_factory.post("/api/v1/passkeys/authenticate/options")

        payload = PasskeyAuthenticationOptionsRequest(email=None)

        response = get_authentication_options(request, payload)

        assert response.challenge_id is not None
        assert response.options is not None
        assert "challenge" in response.options
        assert "rpId" in response.options

    def test_with_email_includes_user_credentials(self, request_factory: RequestFactory):
        """Should include user's credentials when email provided."""
        user = UserFactory.create()
        PasskeyFactory.create(user=user, credential_id=b"user_cred")

        request = request_factory.post("/api/v1/passkeys/authenticate/options")
        payload = PasskeyAuthenticationOptionsRequest(email=user.email)

        response = get_authentication_options(request, payload)

        # Should have allowed credentials
        allow_creds = response.options.get("allowCredentials", [])
        assert len(allow_creds) == 1

    def test_with_nonexistent_email_returns_empty_credentials(
        self, request_factory: RequestFactory
    ):
        """Should return empty credentials for non-existent email (no leak)."""
        request = request_factory.post("/api/v1/passkeys/authenticate/options")
        payload = PasskeyAuthenticationOptionsRequest(email="nonexistent@example.com")

        response = get_authentication_options(request, payload)

        # Should not leak user existence - returns empty/null allowCredentials
        allow_creds = response.options.get("allowCredentials")
        assert allow_creds is None or len(allow_creds) == 0


@pytest.mark.django_db
class TestVerifyAuthentication:
    """Tests for POST /passkeys/authenticate/verify endpoint."""

    def test_rejects_invalid_challenge(self, request_factory: RequestFactory):
        """Should reject expired or invalid challenge."""
        request = request_factory.post("/api/v1/passkeys/authenticate/verify")

        payload = PasskeyAuthenticationVerifyRequest(
            challenge_id="invalid_challenge",
            credential={"rawId": "dGVzdA==", "response": {}},
        )

        with pytest.raises(HttpError) as exc_info:
            verify_authentication(request, payload)

        assert exc_info.value.status_code == 401
        assert "expired or invalid" in str(exc_info.value)

    def test_rejects_missing_credential_id(self, request_factory: RequestFactory):
        """Should reject credential without ID."""
        # Create a valid challenge
        from apps.passkeys.services import get_passkey_service

        service = get_passkey_service()
        options = service.generate_authentication_options()

        request = request_factory.post("/api/v1/passkeys/authenticate/verify")
        payload = PasskeyAuthenticationVerifyRequest(
            challenge_id=options.challenge_id,
            credential={"response": {}},  # Missing rawId and id
        )

        with pytest.raises(HttpError) as exc_info:
            verify_authentication(request, payload)

        assert exc_info.value.status_code == 401
        assert "Missing credential ID" in str(exc_info.value)

    def test_rejects_unknown_passkey(self, request_factory: RequestFactory):
        """Should reject unknown passkey."""
        from apps.passkeys.services import get_passkey_service

        service = get_passkey_service()
        options = service.generate_authentication_options()

        request = request_factory.post("/api/v1/passkeys/authenticate/verify")
        payload = PasskeyAuthenticationVerifyRequest(
            challenge_id=options.challenge_id,
            credential={"rawId": "dW5rbm93bg==", "id": "dW5rbm93bg==", "response": {}},
        )

        with pytest.raises(HttpError) as exc_info:
            verify_authentication(request, payload)

        assert exc_info.value.status_code == 401
        assert "Passkey not found" in str(exc_info.value)


@pytest.mark.django_db
class TestListPasskeys:
    """Tests for GET /passkeys/ endpoint."""

    def test_returns_user_passkeys(self, request_factory: RequestFactory):
        """Should return all passkeys for authenticated user."""
        member = MemberFactory.create()
        user = member.user
        PasskeyFactory.create(user=user, name="Passkey 1")
        PasskeyFactory.create(user=user, name="Passkey 2")

        # Create passkey for different user (should not be returned)
        other_member = MemberFactory.create()
        PasskeyFactory.create(user=other_member.user, name="Other User Passkey")

        request = request_factory.get("/api/v1/passkeys/")
        request.auth = AuthContext(user=user, member=member, organization=member.organization)

        response = list_passkeys(request)

        assert len(response.passkeys) == 2
        names = [p.name for p in response.passkeys]
        assert "Passkey 1" in names
        assert "Passkey 2" in names
        assert "Other User Passkey" not in names

    def test_returns_empty_list_when_no_passkeys(self, request_factory: RequestFactory):
        """Should return empty list when user has no passkeys."""
        member = MemberFactory.create()

        request = request_factory.get("/api/v1/passkeys/")
        request.auth = AuthContext(
            user=member.user, member=member, organization=member.organization
        )

        response = list_passkeys(request)

        assert len(response.passkeys) == 0

    def test_passkey_fields(self, request_factory: RequestFactory):
        """Should return all expected passkey fields."""
        member = MemberFactory.create()
        passkey = PasskeyFactory.create(user=member.user, backup_eligible=True, backup_state=False)

        request = request_factory.get("/api/v1/passkeys/")
        request.auth = AuthContext(
            user=member.user, member=member, organization=member.organization
        )

        response = list_passkeys(request)

        assert len(response.passkeys) == 1
        p = response.passkeys[0]
        assert p.id == passkey.id
        assert p.name == passkey.name
        assert p.created_at is not None
        assert p.backup_eligible is True
        assert p.backup_state is False


@pytest.mark.django_db
class TestDeletePasskey:
    """Tests for DELETE /passkeys/{passkey_id} endpoint."""

    def test_deletes_own_passkey(self, request_factory: RequestFactory):
        """Should delete passkey owned by authenticated user."""
        from apps.passkeys.models import Passkey

        member = MemberFactory.create()
        passkey = PasskeyFactory.create(user=member.user, name="To Delete")
        passkey_id = passkey.id

        request = request_factory.delete(f"/api/v1/passkeys/{passkey_id}")
        request.auth = AuthContext(
            user=member.user, member=member, organization=member.organization
        )

        response = delete_passkey(request, passkey_id)

        assert response.success is True

        # Verify passkey was deleted
        assert not Passkey.objects.filter(id=passkey_id).exists()

    def test_rejects_deleting_other_user_passkey(self, request_factory: RequestFactory):
        """Should reject deleting passkey owned by different user."""
        member = MemberFactory.create()
        other_member = MemberFactory.create()
        passkey = PasskeyFactory.create(user=other_member.user, name="Other's Passkey")

        request = request_factory.delete(f"/api/v1/passkeys/{passkey.id}")
        request.auth = AuthContext(
            user=member.user, member=member, organization=member.organization
        )

        with pytest.raises(HttpError) as exc_info:
            delete_passkey(request, passkey.id)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value)

    def test_rejects_nonexistent_passkey(self, request_factory: RequestFactory):
        """Should return 404 for non-existent passkey."""
        member = MemberFactory.create()

        request = request_factory.delete("/api/v1/passkeys/99999")
        request.auth = AuthContext(
            user=member.user, member=member, organization=member.organization
        )

        with pytest.raises(HttpError) as exc_info:
            delete_passkey(request, 99999)

        assert exc_info.value.status_code == 404
