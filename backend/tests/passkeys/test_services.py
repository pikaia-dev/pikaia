"""
Tests for PasskeyService.

Tests passkey registration and authentication flows with mocked WebAuthn responses.
"""

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.core.cache import cache
from webauthn.helpers import bytes_to_base64url

from apps.passkeys.models import Passkey
from apps.passkeys.services import PasskeyService, get_passkey_service
from tests.accounts.factories import MemberFactory, UserFactory
from tests.passkeys.factories import PasskeyFactory


@pytest.fixture
def passkey_service() -> PasskeyService:
    """Get a PasskeyService instance."""
    return get_passkey_service()


@pytest.fixture
def user_with_member(db):
    """Create a user with an organization membership."""
    member = MemberFactory()
    return member.user, member


class TestPasskeyServiceRegistration:
    """Tests for passkey registration flow."""

    @pytest.mark.django_db
    def test_generate_registration_options_returns_challenge(
        self, passkey_service: PasskeyService, user_with_member
    ):
        """Should generate valid registration options with a challenge."""
        user, member = user_with_member

        result = passkey_service.generate_registration_options(user=user, member=member)

        assert result.challenge_id is not None
        assert result.options_json is not None

        options = json.loads(result.options_json)
        assert "challenge" in options
        assert "rp" in options
        assert "user" in options

        # Challenge should be stored in cache
        cache_key = f"passkey:reg:{result.challenge_id}"
        cached = cache.get(cache_key)
        assert cached is not None
        assert cached["user_id"] == user.id
        assert cached["member_id"] == member.id

    @pytest.mark.django_db
    def test_generate_registration_options_excludes_existing_credentials(
        self, passkey_service: PasskeyService, user_with_member
    ):
        """Should exclude already registered credentials."""
        user, member = user_with_member

        # Create an existing passkey for the user
        PasskeyFactory(user=user, credential_id=b"existing_cred_123")

        result = passkey_service.generate_registration_options(user=user, member=member)

        # The excludeCredentials should contain the existing credential
        options = json.loads(result.options_json)
        exclude_creds = options.get("excludeCredentials", [])
        assert len(exclude_creds) == 1

    @pytest.mark.django_db
    def test_verify_registration_expired_challenge(
        self, passkey_service: PasskeyService, user_with_member
    ):
        """Should reject expired or invalid challenge."""
        user, _ = user_with_member

        with pytest.raises(ValueError, match="expired or invalid"):
            passkey_service.verify_registration(
                user=user,
                challenge_id="nonexistent_challenge",
                credential_json={},
                passkey_name="Test Passkey",
            )

    @pytest.mark.django_db
    def test_verify_registration_wrong_user(
        self, passkey_service: PasskeyService, user_with_member
    ):
        """Should reject challenge created for different user."""
        user, member = user_with_member
        other_user = UserFactory()

        # Create challenge for user
        options = passkey_service.generate_registration_options(user=user, member=member)

        # Try to verify with other_user
        with pytest.raises(ValueError, match="does not match"):
            passkey_service.verify_registration(
                user=other_user,
                challenge_id=options.challenge_id,
                credential_json={},
                passkey_name="Test Passkey",
            )

    @pytest.mark.django_db
    @patch("apps.passkeys.services.verify_registration_response")
    def test_verify_registration_success(
        self, mock_verify, passkey_service: PasskeyService, user_with_member
    ):
        """Should create passkey on successful verification."""
        user, member = user_with_member

        # Generate options
        options = passkey_service.generate_registration_options(user=user, member=member)

        # Mock webauthn verification
        mock_verification = MagicMock()
        mock_verification.credential_id = b"new_credential_id_123"
        mock_verification.credential_public_key = b"public_key_bytes"
        mock_verification.sign_count = 0
        mock_verification.aaguid = uuid4()
        mock_verification.credential_backed_up = False
        mock_verify.return_value = mock_verification

        credential_json = {
            "id": "bmV3X2NyZWRlbnRpYWxfaWRfMTIz",
            "rawId": "bmV3X2NyZWRlbnRpYWxfaWRfMTIz",
            "response": {
                "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
                "attestationObject": "o2NmbXRkbm9uZQ",
                "transports": ["internal", "hybrid"],
            },
            "type": "public-key",
        }

        passkey = passkey_service.verify_registration(
            user=user,
            challenge_id=options.challenge_id,
            credential_json=credential_json,
            passkey_name="My New Passkey",
        )

        assert passkey.id is not None
        assert passkey.user == user
        assert passkey.name == "My New Passkey"
        assert passkey.credential_id == b"new_credential_id_123"
        assert passkey.transports == ["internal", "hybrid"]

        # Verify in DB
        assert Passkey.objects.filter(id=passkey.id).exists()

    @pytest.mark.django_db
    @patch("apps.passkeys.services.verify_registration_response")
    def test_verify_registration_updates_existing_passkey_same_user(
        self, mock_verify, passkey_service: PasskeyService, user_with_member
    ):
        """Should update name if same user re-registers same credential."""
        user, member = user_with_member

        # Create existing passkey
        existing = PasskeyFactory(user=user, credential_id=b"same_credential", name="Old Name")

        # Generate options
        options = passkey_service.generate_registration_options(user=user, member=member)

        # Mock verification returning same credential
        mock_verification = MagicMock()
        mock_verification.credential_id = b"same_credential"
        mock_verification.credential_public_key = b"public_key_bytes"
        mock_verification.sign_count = 0
        mock_verification.aaguid = uuid4()
        mock_verification.credential_backed_up = False
        mock_verify.return_value = mock_verification

        passkey = passkey_service.verify_registration(
            user=user,
            challenge_id=options.challenge_id,
            credential_json={"response": {}},
            passkey_name="New Name",
        )

        # Should return same passkey with updated name
        assert passkey.id == existing.id
        assert passkey.name == "New Name"

    @pytest.mark.django_db
    @patch("apps.passkeys.services.verify_registration_response")
    def test_verify_registration_rejects_credential_owned_by_other_user(
        self, mock_verify, passkey_service: PasskeyService, user_with_member
    ):
        """Should reject credential already registered to active user."""
        user, member = user_with_member
        other_member = MemberFactory()  # Other user with active membership

        # Create passkey owned by other user
        PasskeyFactory(user=other_member.user, credential_id=b"taken_credential")

        # Generate options
        options = passkey_service.generate_registration_options(user=user, member=member)

        # Mock verification returning same credential
        mock_verification = MagicMock()
        mock_verification.credential_id = b"taken_credential"
        mock_verification.credential_public_key = b"public_key_bytes"
        mock_verification.sign_count = 0
        mock_verification.aaguid = uuid4()
        mock_verification.credential_backed_up = False
        mock_verify.return_value = mock_verification

        with pytest.raises(ValueError, match="already registered to another account"):
            passkey_service.verify_registration(
                user=user,
                challenge_id=options.challenge_id,
                credential_json={"response": {}},
                passkey_name="Test",
            )


class TestPasskeyServiceAuthentication:
    """Tests for passkey authentication flow."""

    @pytest.mark.django_db
    def test_generate_authentication_options_returns_challenge(
        self, passkey_service: PasskeyService
    ):
        """Should generate valid authentication options."""
        result = passkey_service.generate_authentication_options()

        assert result.challenge_id is not None
        assert result.options_json is not None

        options = json.loads(result.options_json)
        assert "challenge" in options
        assert "rpId" in options

        # Challenge should be stored in cache
        cache_key = f"passkey:auth:{result.challenge_id}"
        cached = cache.get(cache_key)
        assert cached is not None

    @pytest.mark.django_db
    def test_generate_authentication_options_with_email(
        self, passkey_service: PasskeyService, user_with_member
    ):
        """Should filter credentials by email when provided."""
        user, _ = user_with_member
        PasskeyFactory(user=user, credential_id=b"user_cred_123")

        result = passkey_service.generate_authentication_options(email=user.email)

        # Should include allowed credentials for the user
        options = json.loads(result.options_json)
        allow_creds = options.get("allowCredentials")
        assert allow_creds is not None
        assert len(allow_creds) == 1

    @pytest.mark.django_db
    def test_verify_authentication_expired_challenge(self, passkey_service: PasskeyService):
        """Should reject expired or invalid challenge."""
        with pytest.raises(ValueError, match="expired or invalid"):
            passkey_service.verify_authentication(
                challenge_id="nonexistent_challenge",
                credential_json={"rawId": "dGVzdA==", "response": {}},
            )

    @pytest.mark.django_db
    def test_verify_authentication_unknown_credential(self, passkey_service: PasskeyService):
        """Should reject unknown credential ID."""
        # Create a valid challenge
        options = passkey_service.generate_authentication_options()

        with pytest.raises(ValueError, match="Passkey not found"):
            passkey_service.verify_authentication(
                challenge_id=options.challenge_id,
                credential_json={"rawId": "dW5rbm93bg==", "id": "dW5rbm93bg==", "response": {}},
            )

    @pytest.mark.django_db
    def test_verify_authentication_missing_credential_id(self, passkey_service: PasskeyService):
        """Should reject credential without ID."""
        options = passkey_service.generate_authentication_options()

        with pytest.raises(ValueError, match="Missing credential ID"):
            passkey_service.verify_authentication(
                challenge_id=options.challenge_id,
                credential_json={"response": {}},  # Missing rawId and id
            )

    @pytest.mark.django_db
    def test_generate_authentication_options_nonexistent_email(
        self, passkey_service: PasskeyService
    ):
        """Should return empty credentials for non-existent email (no leak)."""
        result = passkey_service.generate_authentication_options(email="nonexistent@example.com")

        # Should return valid options without leaking user existence
        assert result.challenge_id is not None
        options = json.loads(result.options_json)
        # allowCredentials should be None or empty list
        allow_creds = options.get("allowCredentials")
        assert allow_creds is None or len(allow_creds) == 0

    @pytest.mark.django_db
    @patch("apps.passkeys.services.verify_authentication_response")
    def test_verify_authentication_success(self, mock_verify, passkey_service: PasskeyService):
        """Should return authenticated user on successful verification."""
        # Create member with passkey
        member = MemberFactory()
        user = member.user
        passkey = PasskeyFactory(
            user=user,
            credential_id=b"auth_credential_123",
            public_key=b"public_key_data",
            sign_count=5,
        )

        # Generate options
        options = passkey_service.generate_authentication_options(email=user.email)

        # Mock webauthn verification
        mock_verification = MagicMock()
        mock_verification.new_sign_count = 6
        mock_verify.return_value = mock_verification

        credential_json = {
            "rawId": bytes_to_base64url(b"auth_credential_123"),
            "id": bytes_to_base64url(b"auth_credential_123"),
            "response": {
                "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0In0",
                "authenticatorData": "SZYN5YgOjGh0NBcPZHZgW4_krrmihjLHmVzzuoMdl2MFAAAAAQ",
                "signature": "MEUCIQDKwE",
            },
            "type": "public-key",
        }

        result = passkey_service.verify_authentication(
            challenge_id=options.challenge_id,
            credential_json=credential_json,
        )

        assert result.user == user
        assert result.member == member
        assert result.passkey == passkey

        # Verify sign count was updated
        passkey.refresh_from_db()
        assert passkey.sign_count == 6
        assert passkey.last_used_at is not None

    @pytest.mark.django_db
    @patch("apps.passkeys.services.verify_authentication_response")
    def test_verify_authentication_with_organization_id(
        self, mock_verify, passkey_service: PasskeyService
    ):
        """Should filter by organization when specified."""
        # Create user with two memberships
        user = UserFactory()
        _member1 = MemberFactory(user=user)
        member2 = MemberFactory(user=user)
        _passkey = PasskeyFactory(user=user, credential_id=b"multi_org_cred")

        # Generate options
        options = passkey_service.generate_authentication_options()

        # Mock verification
        mock_verification = MagicMock()
        mock_verification.new_sign_count = 1
        mock_verify.return_value = mock_verification

        credential_json = {
            "rawId": bytes_to_base64url(b"multi_org_cred"),
            "id": bytes_to_base64url(b"multi_org_cred"),
            "response": {},
            "type": "public-key",
        }

        # Specify member2's organization
        result = passkey_service.verify_authentication(
            challenge_id=options.challenge_id,
            credential_json=credential_json,
            organization_id=member2.organization.stytch_org_id,
        )

        assert result.member == member2

    @pytest.mark.django_db
    @patch("apps.passkeys.services.verify_authentication_response")
    def test_verify_authentication_rejects_wrong_organization(
        self, mock_verify, passkey_service: PasskeyService
    ):
        """Should reject if user not member of specified organization."""
        member = MemberFactory()
        _passkey = PasskeyFactory(user=member.user, credential_id=b"wrong_org_cred")

        options = passkey_service.generate_authentication_options()

        mock_verification = MagicMock()
        mock_verification.new_sign_count = 1
        mock_verify.return_value = mock_verification

        credential_json = {
            "rawId": bytes_to_base64url(b"wrong_org_cred"),
            "id": bytes_to_base64url(b"wrong_org_cred"),
            "response": {},
        }

        with pytest.raises(ValueError, match="not a member of the specified organization"):
            passkey_service.verify_authentication(
                challenge_id=options.challenge_id,
                credential_json=credential_json,
                organization_id="org-nonexistent-123",
            )

    @pytest.mark.django_db
    @patch("apps.passkeys.services.verify_authentication_response")
    def test_verify_authentication_user_no_memberships(
        self, mock_verify, passkey_service: PasskeyService
    ):
        """Should reject if user has no organization memberships."""
        # Create user without any membership
        user = UserFactory()
        _passkey = PasskeyFactory(user=user, credential_id=b"no_membership_cred")

        options = passkey_service.generate_authentication_options()

        mock_verification = MagicMock()
        mock_verification.new_sign_count = 1
        mock_verify.return_value = mock_verification

        credential_json = {
            "rawId": bytes_to_base64url(b"no_membership_cred"),
            "id": bytes_to_base64url(b"no_membership_cred"),
            "response": {},
        }

        with pytest.raises(ValueError, match="no organization memberships"):
            passkey_service.verify_authentication(
                challenge_id=options.challenge_id,
                credential_json=credential_json,
            )


class TestPasskeyModel:
    """Tests for Passkey model."""

    @pytest.mark.django_db
    def test_create_passkey(self):
        """Should create a passkey with all fields."""
        passkey = PasskeyFactory()

        assert passkey.id is not None
        assert passkey.user is not None
        assert passkey.credential_id is not None
        assert passkey.public_key is not None
        assert passkey.name is not None
        assert passkey.created_at is not None

    @pytest.mark.django_db
    def test_credential_id_b64_property(self):
        """Should return base64url encoded credential ID."""
        passkey = PasskeyFactory(credential_id=b"test_credential")

        # Should be base64url encoded without padding
        assert passkey.credential_id_b64 == "dGVzdF9jcmVkZW50aWFs"

    @pytest.mark.django_db
    def test_passkey_str(self):
        """Should have readable string representation."""
        user = UserFactory(email="test@example.com")
        passkey = PasskeyFactory(user=user, name="My iPhone")

        assert str(passkey) == "My iPhone (test@example.com)"
