"""
API tests for device linking endpoints.

Tests the service layer and API endpoint behavior.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory

from apps.core.auth import AuthContext
from apps.devices.api import (
    complete_link,
    delete_device,
    initiate_link,
    list_devices,
    refresh_session,
)
from apps.devices.schemas import CompleteLinkRequest, SessionRefreshRequest
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory
from tests.conftest import make_request_with_auth
from tests.devices.factories import DeviceFactory, DeviceLinkTokenFactory

# Test RSA keys for JWT signing
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


def _configure_test_settings(settings) -> None:
    """Configure settings for device linking tests."""
    from apps.passkeys.trusted_auth import get_signing_public_key

    get_signing_public_key.cache_clear()

    settings.PASSKEY_JWT_PRIVATE_KEY = TEST_PRIVATE_KEY
    settings.STYTCH_TRUSTED_AUTH_ISSUER = "test-issuer"
    settings.STYTCH_TRUSTED_AUTH_AUDIENCE = "test-audience"
    settings.JWT_SIGNING_KEY_ID = "test-key-1"
    settings.DEVICE_LINK_TOKEN_EXPIRY_SECONDS = 300
    settings.DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR = 5
    settings.DEVICE_LINK_COMPLETE_MAX_ATTEMPTS_PER_HOUR = 20
    settings.DEVICE_SESSION_EXPIRY_MINUTES = 480
    settings.DEVICE_LINK_URL_SCHEME = "pikaia://device/link"
    settings.STYTCH_TRUSTED_AUTH_PROFILE_ID = "test-profile"


@pytest.mark.django_db
class TestInitiateLinkEndpoint:
    """Tests for initiate_link endpoint."""

    def test_returns_qr_url(self, request_factory: RequestFactory, settings) -> None:
        """Should return QR URL for authenticated user."""
        _configure_test_settings(settings)

        organization = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=organization)

        request = request_factory.post("/")
        request = make_request_with_auth(  # type: ignore[assignment]
            request, AuthContext(user=user, member=member, organization=organization)
        )
        response = initiate_link(request)

        assert response.qr_url.startswith("pikaia://device/link?token=")
        assert response.expires_in_seconds >= 299  # Allow 1 second timing tolerance

    def test_rate_limits_after_max_attempts(
        self, request_factory: RequestFactory, settings
    ) -> None:
        """Should return error when rate limit exceeded."""
        _configure_test_settings(settings)
        settings.DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR = 2

        organization = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=organization)

        # Create tokens to hit rate limit
        for _ in range(2):
            DeviceLinkTokenFactory.create(user=user, member=member, organization=organization)

        request = request_factory.post("/")
        request = make_request_with_auth(  # type: ignore[assignment]
            request, AuthContext(user=user, member=member, organization=organization)
        )

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            initiate_link(request)
        assert exc_info.value.status_code == 429


@pytest.mark.django_db
class TestCompleteLinkEndpoint:
    """Tests for complete_link endpoint."""

    def test_returns_session_on_success(self, request_factory: RequestFactory, settings) -> None:
        """Should return session tokens on successful link."""
        _configure_test_settings(settings)

        organization = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=organization)

        from apps.devices.services import create_link_token

        result = create_link_token(user, member, organization)
        token = result.qr_url.split("token=")[1]

        mock_response = MagicMock()
        mock_response.session_token = "test-session-token"
        mock_response.session_jwt = "test-session-jwt"

        request = request_factory.post("/api/devices/link/complete")

        payload = CompleteLinkRequest(
            token=token,
            device_uuid="test-uuid-123",
            name="iPhone 15",
            platform="ios",
            os_version="17.2",
            app_version="1.0.0",
        )

        with patch("apps.devices.services.get_stytch_client") as mock_client:
            mock_client.return_value.sessions.attest.return_value = mock_response
            response = complete_link(request, payload)

        assert response.session_token == "test-session-token"
        assert response.session_jwt == "test-session-jwt"

    def test_rejects_invalid_token(self, request_factory: RequestFactory, settings) -> None:
        """Should reject invalid token."""
        _configure_test_settings(settings)

        request = request_factory.post("/api/devices/link/complete")
        payload = CompleteLinkRequest(
            token="invalid-token",
            device_uuid="test-uuid",
            name="Test Device",
            platform="ios",
        )

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            complete_link(request, payload)
        assert exc_info.value.status_code == 400


@pytest.mark.django_db
class TestListDevicesEndpoint:
    """Tests for list_devices endpoint."""

    def test_returns_user_devices(self, request_factory: RequestFactory, settings) -> None:
        """Should return only the authenticated user's devices."""
        _configure_test_settings(settings)

        user = UserFactory.create()
        other_user = UserFactory.create()
        organization = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=organization)

        DeviceFactory.create(user=user, name="My iPhone")
        DeviceFactory.create(user=user, name="My iPad")
        DeviceFactory.create(user=other_user, name="Other Device")

        request = request_factory.get("/")
        request = make_request_with_auth(  # type: ignore[assignment]
            request, AuthContext(user=user, member=member, organization=organization)
        )
        response = list_devices(request)

        assert response.count == 2
        device_names = [d.name for d in response.devices]
        assert "My iPhone" in device_names
        assert "My iPad" in device_names
        assert "Other Device" not in device_names

    def test_excludes_revoked_devices(self, request_factory: RequestFactory, settings) -> None:
        """Should not return revoked devices."""
        _configure_test_settings(settings)

        user = UserFactory.create()
        organization = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=organization)

        DeviceFactory.create(user=user, name="Active")
        revoked_device = DeviceFactory.create(user=user, name="Revoked")
        revoked_device.revoke()

        request = request_factory.get("/")
        request = make_request_with_auth(  # type: ignore[assignment]
            request, AuthContext(user=user, member=member, organization=organization)
        )
        response = list_devices(request)

        assert response.count == 1
        assert response.devices[0].name == "Active"


@pytest.mark.django_db
class TestRevokeDeviceEndpoint:
    """Tests for delete_device endpoint."""

    def test_revokes_own_device(self, request_factory: RequestFactory, settings) -> None:
        """Should successfully revoke user's own device."""
        _configure_test_settings(settings)

        user = UserFactory.create()
        organization = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=organization)

        device = DeviceFactory.create(user=user)

        request = request_factory.delete("/")
        request = make_request_with_auth(  # type: ignore[assignment]
            request, AuthContext(user=user, member=member, organization=organization)
        )
        status, _ = delete_device(request, device.id)

        assert status == 204
        device.refresh_from_db()
        assert device.is_revoked

    def test_returns_404_for_other_users_device(
        self, request_factory: RequestFactory, settings
    ) -> None:
        """Should return 404 when trying to revoke another user's device."""
        _configure_test_settings(settings)

        user = UserFactory.create()
        other_user = UserFactory.create()
        organization = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=organization)

        other_device = DeviceFactory.create(user=other_user)

        request = request_factory.delete("/")
        request = make_request_with_auth(  # type: ignore[assignment]
            request, AuthContext(user=user, member=member, organization=organization)
        )

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            delete_device(request, other_device.id)
        assert exc_info.value.status_code == 404


@pytest.mark.django_db
class TestSessionRefreshEndpoint:
    """Tests for refresh_session endpoint."""

    def test_refreshes_session_for_linked_device(
        self, request_factory: RequestFactory, settings
    ) -> None:
        """Should return new session tokens for valid device."""
        _configure_test_settings(settings)

        user = UserFactory.create()
        organization = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=organization)
        device = DeviceFactory.create(user=user)

        mock_response = MagicMock()
        mock_response.session_token = "new-session-token"
        mock_response.session_jwt = "new-session-jwt"

        request = request_factory.post("/")
        request = make_request_with_auth(  # type: ignore[assignment]
            request, AuthContext(user=user, member=member, organization=organization)
        )
        payload = SessionRefreshRequest(device_uuid=device.device_uuid)

        with patch("apps.devices.services.get_stytch_client") as mock_client:
            mock_client.return_value.sessions.attest.return_value = mock_response
            response = refresh_session(request, payload)

        assert response.session_token == "new-session-token"
        assert response.session_jwt == "new-session-jwt"

    def test_returns_404_for_unlinked_device(
        self, request_factory: RequestFactory, settings
    ) -> None:
        """Should return 404 for device not linked to user."""
        _configure_test_settings(settings)

        user = UserFactory.create()
        organization = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=organization)

        request = request_factory.post("/")
        request = make_request_with_auth(  # type: ignore[assignment]
            request, AuthContext(user=user, member=member, organization=organization)
        )
        payload = SessionRefreshRequest(device_uuid="unknown-device")

        from ninja.errors import HttpError

        with pytest.raises(HttpError) as exc_info:
            refresh_session(request, payload)
        assert exc_info.value.status_code == 404
