"""
Tests for PasskeyService.

Tests passkey registration and authentication flows with mocked WebAuthn responses.
"""

from unittest.mock import MagicMock, patch
import json
import pytest
from django.core.cache import cache

from apps.passkeys.services import PasskeyService, get_passkey_service
from apps.passkeys.models import Passkey
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
