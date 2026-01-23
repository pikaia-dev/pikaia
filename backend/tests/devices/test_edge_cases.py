"""
Edge case tests for device linking.

Tests unusual scenarios and boundary conditions.
"""

import hashlib
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from django.utils import timezone

from apps.devices.exceptions import RateLimitError, TokenExpiredError, TokenInvalidError
from apps.devices.models import DeviceLinkToken
from apps.devices.services import (
    complete_device_link,
    create_link_token,
)
from tests.accounts.factories import MemberFactory, UserFactory
from tests.devices.factories import DeviceFactory, DeviceLinkTokenFactory

# Test RSA private key (same as services tests)
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
class TestTokenEdgeCases:
    """Edge cases for token validation."""

    def test_rejects_token_with_wrong_action(self, settings) -> None:
        """Should reject JWT with wrong action claim."""
        _configure_test_settings(settings)

        now = int(time.time())
        payload = {
            "jti": "test",
            "iat": now,
            "exp": now + 300,
            "sub": "1",
            "action": "wrong_action",  # Wrong action
            "email": "test@example.com",
            "org_id": "org-123",
            "member_id": "member-123",
        }
        token = jwt.encode(payload, TEST_PRIVATE_KEY, algorithm="RS256")

        with pytest.raises(TokenInvalidError, match="Invalid token type"):
            complete_device_link(
                token=token,
                device_uuid="test-uuid",
                name="Test Device",
                platform="ios",
            )

    def test_rejects_token_not_in_database(self, settings) -> None:
        """Should reject valid JWT that is not stored in database."""
        _configure_test_settings(settings)

        # Create valid JWT but don't store it in DB
        now = int(time.time())
        payload = {
            "jti": str(timezone.now().timestamp()),
            "iat": now,
            "exp": now + 300,
            "sub": "1",
            "action": "device_link",
            "email": "test@example.com",
            "org_id": "org-123",
            "member_id": "member-123",
        }
        token = jwt.encode(
            payload,
            TEST_PRIVATE_KEY,
            algorithm="RS256",
            headers={"kid": settings.JWT_SIGNING_KEY_ID},
        )

        with pytest.raises(TokenInvalidError, match="not found"):
            complete_device_link(
                token=token,
                device_uuid="test-uuid",
                name="Test Device",
                platform="ios",
            )

    def test_token_record_expired_but_jwt_valid(self, settings) -> None:
        """Should reject when token record is expired even if JWT isn't."""
        _configure_test_settings(settings)
        member = MemberFactory.create()

        # Create token normally
        result = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )
        token = result.qr_url.split("?token=")[1]

        # Manually expire the token record in DB
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        token_record = DeviceLinkToken.objects.get(token_hash=token_hash)
        token_record.expires_at = timezone.now() - timedelta(minutes=1)
        token_record.save()

        with pytest.raises(TokenExpiredError, match="expired"):
            complete_device_link(
                token=token,
                device_uuid="test-uuid",
                name="Test Device",
                platform="ios",
            )


@pytest.mark.django_db
class TestRelinkingEdgeCases:
    """Edge cases for device re-linking."""

    @patch("apps.devices.services._create_mobile_session")
    def test_relinking_active_device_same_user_updates_fields(
        self, mock_session: MagicMock, settings
    ) -> None:
        """Re-linking an active device to same user should update fields."""
        _configure_test_settings(settings)
        mock_session.return_value = ("session_token", "session_jwt")
        member = MemberFactory.create()

        # Create existing active device
        existing = DeviceFactory.create(
            user=member.user,
            device_uuid="my-device-uuid",
            name="Old Name",
            platform="android",
            os_version="12.0",
            app_version="0.9.0",
        )
        original_id = existing.id

        # Re-link with new info
        result = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )
        token = result.qr_url.split("?token=")[1]

        link_result = complete_device_link(
            token=token,
            device_uuid="my-device-uuid",
            name="New Name",
            platform="ios",
            os_version="17.2",
            app_version="1.0.0",
        )

        # Should be same device (same ID)
        assert link_result.device.id == original_id

        # Fields should be updated
        link_result.device.refresh_from_db()
        assert link_result.device.name == "New Name"
        assert link_result.device.platform == "ios"
        assert link_result.device.os_version == "17.2"
        assert link_result.device.app_version == "1.0.0"

    @patch("apps.devices.services._create_mobile_session")
    def test_revoked_device_relinked_gets_new_user(self, mock_session: MagicMock, settings) -> None:
        """Revoked device can be reassigned to different user."""
        _configure_test_settings(settings)
        mock_session.return_value = ("session_token", "session_jwt")

        user1 = UserFactory.create()
        member2 = MemberFactory.create()

        # User1's revoked device
        device = DeviceFactory.create(
            user=user1,
            device_uuid="recycled-uuid",
            name="Old Device",
        )
        original_id = device.id
        device.revoke()

        # User2 links the same device
        result = create_link_token(
            user=member2.user,
            member=member2,
            organization=member2.organization,
        )
        token = result.qr_url.split("?token=")[1]

        link_result = complete_device_link(
            token=token,
            device_uuid="recycled-uuid",
            name="New Owner Device",
            platform="ios",
        )

        # Same device record (same ID)
        assert link_result.device.id == original_id

        # But now owned by user2
        assert link_result.device.user == member2.user
        assert link_result.device.revoked_at is None


@pytest.mark.django_db
class TestRateLimitEdgeCases:
    """Edge cases for rate limiting."""

    def test_old_tokens_dont_count_toward_limit(self, settings) -> None:
        """Tokens created more than 1 hour ago should not count toward limit."""
        _configure_test_settings(settings)
        settings.DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR = 2
        member = MemberFactory.create()

        # Create old tokens (more than 1 hour ago)
        old_time = timezone.now() - timedelta(hours=2)
        DeviceLinkTokenFactory.create(
            user=member.user,
            member=member,
            organization=member.organization,
            created_at=old_time,
        )
        # Force update created_at since auto_now_add
        DeviceLinkToken.objects.filter(user=member.user).update(created_at=old_time)

        # Should be able to create 2 new tokens (limit is 2)
        result1 = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )
        result2 = create_link_token(
            user=member.user,
            member=member,
            organization=member.organization,
        )

        assert result1.qr_url is not None
        assert result2.qr_url is not None

    def test_used_tokens_still_count_toward_limit(self, settings) -> None:
        """Used tokens within the hour should still count toward rate limit."""
        _configure_test_settings(settings)
        settings.DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR = 2
        member = MemberFactory.create()

        # Create and use tokens
        DeviceLinkTokenFactory.create(
            user=member.user,
            member=member,
            organization=member.organization,
            used_at=timezone.now(),
        )
        DeviceLinkTokenFactory.create(
            user=member.user,
            member=member,
            organization=member.organization,
            used_at=timezone.now(),
        )

        # Should hit rate limit
        with pytest.raises(RateLimitError):
            create_link_token(
                user=member.user,
                member=member,
                organization=member.organization,
            )


@pytest.mark.django_db
class TestDeviceUniqueConstraint:
    """Test device_uuid unique constraint handling."""

    def test_device_uuid_must_be_unique(self, settings) -> None:
        """Should enforce unique device_uuid constraint."""
        _configure_test_settings(settings)
        user = UserFactory.create()

        DeviceFactory.create(user=user, device_uuid="unique-uuid-123")

        # Trying to create another device with same uuid should fail
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            DeviceFactory.create(user=user, device_uuid="unique-uuid-123")
