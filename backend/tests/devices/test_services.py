"""
Tests for device linking services.

Tests token creation, device linking, revocation, and listing.
"""

import hashlib
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from django.utils import timezone

from apps.devices.exceptions import (
    DeviceAlreadyLinkedError,
    RateLimitError,
    TokenExpiredError,
    TokenInvalidError,
    TokenUsedError,
)
from apps.devices.models import Device, DeviceLinkToken
from apps.devices.services import (
    complete_device_link,
    create_link_token,
    list_user_devices,
    revoke_device,
)
from tests.accounts.factories import MemberFactory, UserFactory
from tests.devices.factories import DeviceFactory

# Test RSA private key (same as passkeys tests)
TEST_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCVyLhf1ZHrknFF
mBkLsYZ3KugyQNXVQOSKW/s9+wEOamKhtysC3ImNeJpxir4bCM6v0e32lJxWOjTu
/Hfr2qJZVjhWMmK3IGNm1042sQpLPIBE5KRbYE49kNgV6VY4oA6MWTjeHYsMT9fQ
LG9nxdtoAJVhTUFfiX/jM5n5kVDFZ5kdTJmECrBWCbgNjbEdsXHM0ZEFM47GXe6t
V2QEwdixaNUYN2GbxPNInSNWXL2Sh/zhPR5tEoIQSrupZxH+auy2pTyT0xKcaRqV
b9/KLaGK+uz+/3Ct4OBKHZgUBcNRTqtSKO/nZ883xQWHe6oIVw6PMlQvmqTnRu6Q
NtHdhDB1AgMBAAECggEAE0GiXoO9Bk2l7V4P/j5c/K4R+v/13bxBhX4szzuZV6qa
spKzX2NN9dem92jwZtZbiCQTlUtmy/kgvAbOPg62J4kbpg1FPqjVzq9oeUSKf8Cv
9ut0K+E2PdkExtBgSthc9nM0Ce4/ZZ5QLw2/ZtZ7jiPhEIjXmjo5rFKCfaDOgwpL
ugDswnKmom3rieiYkVdyhq3TWVn/aUO8ReP9aCCKn3jCxU65l7TLe2zP9jT136yj
H3Umkhfhx9qmKzFWfLzhAThID7TKjchiFWk69u3ti9IpLwpdgTTRPcPvHKqVSkCG
otUGvWTC/b0uOygh9/jXPi4gAXlSC04T5+I+nc6PYQKBgQDIuZwNVMYlpI1+rVe3
vaKI9pWO2ezPltH6VBQ/p5KFAKOCogININmCsw36pDO8XuEwx8rZ8SBRiI4ytN14
bLN98Ee5qG1fwpf+aSrAx5ePukuhRWHezFueadJu4/utaC4W51mTqwiLnd8Vrgxx
56tFizmL/sXjTzgBRxFH8vlLJQKBgQC/B/S0vGOEBYaOPlA95JezvK+eWjWC2bUj
h/g4rBAs/wNUEe0cQbmuKnJjiKxaIan2nm25aM475t7p6kxDr8kX9wQ4OI/Rbheq
aA5bmyW14Ya/jsmvnAXMWTdmXNmMbaMkm8yX2gEIH+LeeYQ187VlLFdFO59mxcRr
RiJRamh3EQKBgQCIn83YRRuaA6dL0jEin7FCCJVD5pGJut6xxQkDSswwO38QK7W5
ueJTVAzvzVRpoyskSNmJ/tZAqPIhEXqtvU9vKV2owTuxMoLCaFLxZOmEqwlPfCph
vDegW+cgE437Oi4k6NPP71qhrZNq7k0KOuYZL+q7n26SihlUxUq97mRBAQKBgAJe
qeV4FM/1dZbcJQivhkY/h/ox6koGQ13+eNDTKZw1SahIVKWuFwyXEDY14tV3Z3Fc
w8WyDCToF0nVkz6ftqHqeY3s/bO+ZuLBSbRPN2eLNa24qr3X9KZ1UN+fNT+tuIFi
wWX82VhtdNYHseEtdcmchDSiqbaPq4EdLJ3P8R3RAoGBALm5Zw2SXhxoE2fLBhHR
xumRVJIf+sm3hli9H0F9CpO6/+E0fRHuWk2jN0tYOErKwUBqPCfk5/Efy8Zy+e4r
b8jC/mQIlWNM1U+IGB6DHVoLIw4NR5pK8jcwR5ueNzPxr2EPPmZ6+zCk3C9Mjh7z
4KyGKoZ7tWAsxd0P/iVOEAfc
-----END PRIVATE KEY-----"""


def _configure_test_settings(settings):
    """Configure settings for device linking tests."""
    # Clear the cached public key so it's regenerated from the new private key
    from apps.passkeys.trusted_auth import get_signing_public_key

    get_signing_public_key.cache_clear()

    settings.PASSKEY_JWT_PRIVATE_KEY = TEST_PRIVATE_KEY
    settings.STYTCH_TRUSTED_AUTH_ISSUER = "test-issuer"
    settings.STYTCH_TRUSTED_AUTH_AUDIENCE = "test-audience"
    settings.JWT_SIGNING_KEY_ID = "test-key-1"
    settings.DEVICE_LINK_TOKEN_EXPIRY_SECONDS = 300
    settings.DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR = 5
    settings.DEVICE_SESSION_EXPIRY_MINUTES = 480
    settings.DEVICE_LINK_URL_SCHEME = "pikaia://device/link"
    settings.STYTCH_TRUSTED_AUTH_PROFILE_ID = "test-profile"


@pytest.mark.django_db
class TestCreateLinkToken:
    """Tests for create_link_token service."""

    def test_creates_token_with_correct_qr_url(self, settings) -> None:
        """Should create token with correct QR URL format."""
        _configure_test_settings(settings)
        member = MemberFactory.create()

        result = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )

        assert result.qr_url.startswith("pikaia://device/link?token=")
        assert result.expires_at is not None
        assert result.token_record is not None

    def test_creates_valid_jwt_in_qr_url(self, settings) -> None:
        """Should create JWT with correct claims in QR URL."""
        _configure_test_settings(settings)
        member = MemberFactory.create()

        result = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )

        # Extract token from URL
        token = result.qr_url.split("?token=")[1]

        # Decode without verification to inspect claims
        decoded = jwt.decode(token, options={"verify_signature": False})

        assert decoded["sub"] == str(member.user.id)
        assert decoded["email"] == member.user.email
        assert decoded["action"] == "device_link"
        assert decoded["org_id"] == member.organization.stytch_org_id
        assert decoded["member_id"] == member.stytch_member_id

    def test_stores_token_hash_not_token(self, settings) -> None:
        """Should store SHA-256 hash of token, not the token itself."""
        _configure_test_settings(settings)
        member = MemberFactory.create()

        result = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )

        token = result.qr_url.split("?token=")[1]
        expected_hash = hashlib.sha256(token.encode()).hexdigest()

        assert result.token_record.token_hash == expected_hash

    def test_sets_expiration_to_5_minutes(self, settings) -> None:
        """Should set token expiration to 5 minutes."""
        _configure_test_settings(settings)
        member = MemberFactory.create()

        before = timezone.now()
        result = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )
        after = timezone.now()

        # Should expire ~5 minutes from creation
        expected_min = before + timedelta(seconds=300)
        expected_max = after + timedelta(seconds=300)

        assert expected_min <= result.expires_at <= expected_max

    def test_rate_limits_after_max_attempts(self, settings) -> None:
        """Should raise RateLimitError after max attempts per hour."""
        _configure_test_settings(settings)
        settings.DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR = 2
        member = MemberFactory.create()

        # Create max allowed tokens
        create_link_token(user=member.user, member=member, organization=member.organization)
        create_link_token(user=member.user, member=member, organization=member.organization)

        # Next attempt should fail
        with pytest.raises(RateLimitError, match="Too many link attempts"):
            create_link_token(user=member.user, member=member, organization=member.organization)

    def test_rate_limit_is_per_user(self, settings) -> None:
        """Should rate limit per user, not globally."""
        _configure_test_settings(settings)
        settings.DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR = 2

        member1 = MemberFactory.create()
        member2 = MemberFactory.create()

        # User 1 hits limit
        create_link_token(user=member1.user, member=member1, organization=member1.organization)
        create_link_token(user=member1.user, member=member1, organization=member1.organization)

        # User 2 should still be able to create tokens
        result = create_link_token(
            user=member2.user, member=member2, organization=member2.organization
        )
        assert result.qr_url is not None


@pytest.mark.django_db
class TestCompleteDeviceLink:
    """Tests for complete_device_link service."""

    def _create_valid_token(self, settings, member):
        """Helper to create a valid token for testing."""
        _configure_test_settings(settings)
        result = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )
        return result.qr_url.split("?token=")[1]

    @patch("apps.devices.services._create_mobile_session")
    def test_creates_device_on_valid_token(self, mock_session: MagicMock, settings) -> None:
        """Should create device record on valid token."""
        mock_session.return_value = ("session_token", "session_jwt", timezone.now())
        member = MemberFactory.create()
        token = self._create_valid_token(settings, member)

        result = complete_device_link(
            token=token,
            device_uuid="test-uuid-123",
            name="iPhone 15 Pro",
            platform="ios",
            os_version="17.2",
            app_version="1.0.0",
        )

        assert result.device is not None
        assert result.device.device_uuid == "test-uuid-123"
        assert result.device.name == "iPhone 15 Pro"
        assert result.device.platform == "ios"
        assert result.device.user == member.user

    @patch("apps.devices.services._create_mobile_session")
    def test_returns_session_tokens(self, mock_session: MagicMock, settings) -> None:
        """Should return both session_token and session_jwt."""
        mock_session.return_value = ("test_session_token", "test_session_jwt", timezone.now())
        member = MemberFactory.create()
        token = self._create_valid_token(settings, member)

        result = complete_device_link(
            token=token,
            device_uuid="test-uuid-123",
            name="Test Device",
            platform="ios",
        )

        assert result.session_token == "test_session_token"
        assert result.session_jwt == "test_session_jwt"

    @patch("apps.devices.services._create_mobile_session")
    def test_marks_token_as_used(self, mock_session: MagicMock, settings) -> None:
        """Should mark token as used after successful link."""
        mock_session.return_value = ("session_token", "session_jwt", timezone.now())
        member = MemberFactory.create()
        token = self._create_valid_token(settings, member)

        complete_device_link(
            token=token,
            device_uuid="test-uuid-123",
            name="Test Device",
            platform="ios",
        )

        # Token should be marked as used
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        token_record = DeviceLinkToken.objects.get(token_hash=token_hash)
        assert token_record.is_used

    def test_rejects_expired_token(self, settings) -> None:
        """Should reject expired JWT."""
        _configure_test_settings(settings)

        # Create expired token manually
        now = int(time.time())
        payload = {
            "jti": "test",
            "iat": now - 600,  # 10 minutes ago
            "exp": now - 300,  # Expired 5 minutes ago
            "sub": "1",
            "action": "device_link",
            "email": "test@example.com",
            "org_id": "org-123",
            "member_id": "member-123",
        }
        token = jwt.encode(payload, TEST_PRIVATE_KEY, algorithm="RS256")

        with pytest.raises(TokenExpiredError, match="expired"):
            complete_device_link(
                token=token,
                device_uuid="test-uuid",
                name="Test Device",
                platform="ios",
            )

    def test_rejects_invalid_token(self, settings) -> None:
        """Should reject malformed token."""
        _configure_test_settings(settings)

        with pytest.raises(TokenInvalidError, match="Invalid"):
            complete_device_link(
                token="not-a-valid-jwt",
                device_uuid="test-uuid",
                name="Test Device",
                platform="ios",
            )

    @patch("apps.devices.services._create_mobile_session")
    def test_rejects_already_used_token(self, mock_session: MagicMock, settings) -> None:
        """Should reject token that has already been used."""
        mock_session.return_value = ("session_token", "session_jwt", timezone.now())
        member = MemberFactory.create()
        token = self._create_valid_token(settings, member)

        # First use succeeds
        complete_device_link(
            token=token,
            device_uuid="device-1",
            name="Device 1",
            platform="ios",
        )

        # Second use fails
        with pytest.raises(TokenUsedError, match="already been used"):
            complete_device_link(
                token=token,
                device_uuid="device-2",
                name="Device 2",
                platform="ios",
            )

    @patch("apps.devices.services._create_mobile_session")
    def test_rejects_device_linked_to_another_user(self, mock_session: MagicMock, settings) -> None:
        """Should reject if device is already linked to different user."""
        mock_session.return_value = ("session_token", "session_jwt", timezone.now())

        # Create device linked to user1
        user1 = UserFactory.create()
        _existing_device = DeviceFactory.create(user=user1, device_uuid="shared-uuid")

        # User2 tries to link same device
        member2 = MemberFactory.create()
        token = self._create_valid_token(settings, member2)

        with pytest.raises(DeviceAlreadyLinkedError, match="already linked"):
            complete_device_link(
                token=token,
                device_uuid="shared-uuid",
                name="Test Device",
                platform="ios",
            )

    @patch("apps.devices.services._create_mobile_session")
    def test_allows_relinking_revoked_device_same_user(
        self, mock_session: MagicMock, settings
    ) -> None:
        """Should allow re-linking a revoked device for the same user."""
        mock_session.return_value = ("session_token", "session_jwt", timezone.now())
        member = MemberFactory.create()

        # Create and revoke device
        device = DeviceFactory.create(user=member.user, device_uuid="my-uuid")
        device.revoke()

        # Should be able to re-link
        token = self._create_valid_token(settings, member)
        result = complete_device_link(
            token=token,
            device_uuid="my-uuid",
            name="Re-linked Device",
            platform="ios",
        )

        assert result.device.device_uuid == "my-uuid"
        assert result.device.revoked_at is None
        assert result.device.name == "Re-linked Device"

    @patch("apps.devices.services._create_mobile_session")
    def test_allows_relinking_revoked_device_different_user(
        self, mock_session: MagicMock, settings
    ) -> None:
        """Should allow linking a revoked device to different user."""
        mock_session.return_value = ("session_token", "session_jwt", timezone.now())

        # User1 has revoked device
        user1 = UserFactory.create()
        device = DeviceFactory.create(user=user1, device_uuid="old-uuid")
        device.revoke()

        # User2 can now link it
        member2 = MemberFactory.create()
        token = self._create_valid_token(settings, member2)
        result = complete_device_link(
            token=token,
            device_uuid="old-uuid",
            name="New Owner Device",
            platform="android",
        )

        assert result.device.user == member2.user
        assert result.device.revoked_at is None


@pytest.mark.django_db
class TestRevokeDevice:
    """Tests for revoke_device service."""

    def test_revokes_owned_device(self) -> None:
        """Should revoke device owned by user."""
        user = UserFactory.create()
        device = DeviceFactory.create(user=user)

        revoke_device(device_id=device.id, user=user)

        device.refresh_from_db()
        assert device.is_revoked
        assert device.revoked_at is not None

    def test_raises_error_for_nonexistent_device(self) -> None:
        """Should raise DoesNotExist for invalid device ID."""
        user = UserFactory.create()

        with pytest.raises(Device.DoesNotExist):
            revoke_device(device_id=99999, user=user)

    def test_raises_error_for_other_users_device(self) -> None:
        """Should raise DoesNotExist when trying to revoke another user's device."""
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        device = DeviceFactory.create(user=user1)

        with pytest.raises(Device.DoesNotExist):
            revoke_device(device_id=device.id, user=user2)


@pytest.mark.django_db
class TestListUserDevices:
    """Tests for list_user_devices service."""

    def test_returns_active_devices_only(self) -> None:
        """Should return only non-revoked devices."""
        user = UserFactory.create()
        _active_device = DeviceFactory.create(user=user, name="Active")
        revoked_device = DeviceFactory.create(user=user, name="Revoked")
        revoked_device.revoke()

        devices = list_user_devices(user)

        assert len(devices) == 1
        assert devices[0].name == "Active"

    def test_returns_only_users_devices(self) -> None:
        """Should return only devices belonging to the user."""
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        DeviceFactory.create(user=user1, name="User1 Device")
        DeviceFactory.create(user=user2, name="User2 Device")

        devices = list_user_devices(user1)

        assert len(devices) == 1
        assert devices[0].name == "User1 Device"

    def test_returns_devices_ordered_by_created_at_desc(self) -> None:
        """Should return devices ordered by creation date, newest first."""
        user = UserFactory.create()
        _old_device = DeviceFactory.create(user=user, name="Old")
        _new_device = DeviceFactory.create(user=user, name="New")

        devices = list_user_devices(user)

        assert len(devices) == 2
        assert devices[0].name == "New"
        assert devices[1].name == "Old"

    def test_returns_empty_list_for_user_without_devices(self) -> None:
        """Should return empty list for user with no devices."""
        user = UserFactory.create()

        devices = list_user_devices(user)

        assert devices == []
