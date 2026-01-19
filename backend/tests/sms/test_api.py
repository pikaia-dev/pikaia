"""
Tests for SMS/OTP API endpoints.
"""

from unittest.mock import patch

import pytest
from django.test import RequestFactory
from ninja.errors import HttpError

from apps.core.auth import AuthContext
from apps.core.types import AuthenticatedHttpRequest
from apps.sms.api import send_verification_otp, verify_phone_otp
from apps.sms.schemas import SendOTPRequest, VerifyOTPRequest
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory
from tests.conftest import make_request_with_auth


@pytest.mark.django_db
class TestSendVerificationOTPEndpoint:
    """Tests for POST /auth/phone/send endpoint."""

    def test_sends_otp_when_authenticated(self, request_factory: RequestFactory) -> None:
        """Should send OTP for authenticated user."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        _member = MemberFactory.create(user=user, organization=org)

        auth_request: AuthenticatedHttpRequest = make_request_with_auth(
            request_factory.post("/api/v1/auth/phone/send"),
            AuthContext(user=user, member=_member, organization=org),
        )

        payload = SendOTPRequest(phone_number="+14155551234")

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}

            result = send_verification_otp(auth_request, payload)

        assert result.success is True
        assert "+14155551234" in result.message
        assert result.expires_in_minutes == 30

    def test_requires_authentication(self, request_factory: RequestFactory) -> None:
        """Should reject unauthenticated requests."""
        request = request_factory.post("/api/v1/auth/phone/send")
        # Don't set auth attributes

        payload = SendOTPRequest(phone_number="+14155551234")

        with pytest.raises(HttpError) as exc_info:
            send_verification_otp(request, payload)  # type: ignore[arg-type]  # Testing unauthenticated

        assert exc_info.value.status_code == 401

    def test_rate_limits_requests(self, request_factory: RequestFactory) -> None:
        """Should return 429 when rate limited."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        auth_request: AuthenticatedHttpRequest = make_request_with_auth(
            request_factory.post("/api/v1/auth/phone/send"),
            AuthContext(user=user, member=member, organization=org),
        )

        payload = SendOTPRequest(phone_number="+14155551234")

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}

            # Send 3 OTPs successfully
            for _ in range(3):
                send_verification_otp(auth_request, payload)

            # 4th should be rate limited
            with pytest.raises(HttpError) as exc_info:
                send_verification_otp(auth_request, payload)

            assert exc_info.value.status_code == 429

    def test_handles_sms_failure(self, request_factory: RequestFactory) -> None:
        """Should return 400 when SMS sending fails."""
        from apps.sms.aws_client import SMSError

        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        auth_request: AuthenticatedHttpRequest = make_request_with_auth(
            request_factory.post("/api/v1/auth/phone/send"),
            AuthContext(user=user, member=member, organization=org),
        )

        payload = SendOTPRequest(phone_number="+14155551234")

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.side_effect = SMSError("AWS error")

            with pytest.raises(HttpError) as exc_info:
                send_verification_otp(auth_request, payload)

            assert exc_info.value.status_code == 400


@pytest.mark.django_db
class TestVerifyPhoneOTPEndpoint:
    """Tests for POST /auth/phone/verify endpoint."""

    def test_verifies_phone_successfully(self, request_factory: RequestFactory) -> None:
        """Should verify phone and return success."""
        user = UserFactory.create(phone_number="", phone_verified_at=None)
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org)
        phone = "+14155551234"

        # First send OTP
        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}

            from apps.sms.services import send_phone_verification_otp

            otp = send_phone_verification_otp(phone, user)

        # Then verify
        auth_request: AuthenticatedHttpRequest = make_request_with_auth(
            request_factory.post("/api/v1/auth/phone/verify"),
            AuthContext(user=user, member=member, organization=org),
        )

        payload = VerifyOTPRequest(phone_number=phone, code=otp.code)

        result = verify_phone_otp(auth_request, payload)

        assert result.success is True
        assert result.phone_verified is True

        # Verify user was updated
        user.refresh_from_db()
        assert user.phone_number == phone
        assert user.phone_verified_at is not None

    def test_requires_authentication(self, request_factory: RequestFactory) -> None:
        """Should reject unauthenticated requests."""
        request = request_factory.post("/api/v1/auth/phone/verify")
        # Don't set auth attributes

        payload = VerifyOTPRequest(phone_number="+14155551234", code="1234")

        with pytest.raises(HttpError) as exc_info:
            verify_phone_otp(request, payload)  # type: ignore[arg-type]  # Testing unauthenticated

        assert exc_info.value.status_code == 401

    def test_rejects_invalid_code(self, request_factory: RequestFactory) -> None:
        """Should return 400 for invalid OTP code."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org)
        phone = "+14155551234"

        # Send OTP
        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}

            from apps.sms.services import send_phone_verification_otp

            send_phone_verification_otp(phone, user)

        # Try to verify with wrong code
        auth_request: AuthenticatedHttpRequest = make_request_with_auth(
            request_factory.post("/api/v1/auth/phone/verify"),
            AuthContext(user=user, member=member, organization=org),
        )

        payload = VerifyOTPRequest(phone_number=phone, code="0000")

        with pytest.raises(HttpError) as exc_info:
            verify_phone_otp(auth_request, payload)

        assert exc_info.value.status_code == 400
        assert "Invalid" in str(exc_info.value.message)

    def test_rejects_expired_otp(self, request_factory: RequestFactory) -> None:
        """Should return 400 for expired OTP."""
        from datetime import timedelta

        from django.utils import timezone

        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org)
        phone = "+14155551234"

        # Send OTP and expire it
        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}

            from apps.sms.services import send_phone_verification_otp

            otp = send_phone_verification_otp(phone, user)

        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()

        # Try to verify
        auth_request: AuthenticatedHttpRequest = make_request_with_auth(
            request_factory.post("/api/v1/auth/phone/verify"),
            AuthContext(user=user, member=member, organization=org),
        )

        payload = VerifyOTPRequest(phone_number=phone, code=otp.code)

        with pytest.raises(HttpError) as exc_info:
            verify_phone_otp(auth_request, payload)

        assert exc_info.value.status_code == 400
        assert "expired" in str(exc_info.value.message).lower()


@pytest.mark.django_db
class TestOTPSchemaValidation:
    """Tests for OTP request schema validation."""

    def test_send_otp_request_valid(self) -> None:
        """Should accept valid phone number."""
        request = SendOTPRequest(phone_number="+14155551234")
        assert request.phone_number == "+14155551234"

    def test_send_otp_request_rejects_short_phone(self) -> None:
        """Should reject phone numbers that are too short."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SendOTPRequest(phone_number="+1415")

    def test_verify_otp_request_valid(self) -> None:
        """Should accept valid verification request."""
        request = VerifyOTPRequest(phone_number="+14155551234", code="1234")
        assert request.phone_number == "+14155551234"
        assert request.code == "1234"

    def test_verify_otp_request_rejects_short_code(self) -> None:
        """Should reject OTP codes that are too short."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            VerifyOTPRequest(phone_number="+14155551234", code="12")
