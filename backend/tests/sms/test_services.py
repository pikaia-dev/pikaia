"""
Tests for SMS/OTP services.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.sms.models import OTPVerification
from apps.sms.services import (
    OTPExpiredError,
    OTPInvalidError,
    OTPMaxAttemptsError,
    OTPRateLimitError,
    cleanup_expired_otps,
    generate_otp_code,
    send_phone_verification_otp,
    verify_otp,
    verify_phone_for_user,
)
from tests.accounts.factories import UserFactory


class TestGenerateOTPCode:
    """Tests for OTP code generation."""

    def test_generates_correct_length(self) -> None:
        """Should generate code with specified length."""
        code = generate_otp_code(4)
        assert len(code) == 4

        code = generate_otp_code(6)
        assert len(code) == 6

    def test_generates_only_digits(self) -> None:
        """Should generate only numeric digits."""
        for _ in range(100):
            code = generate_otp_code(6)
            assert code.isdigit()

    def test_uses_default_length_from_settings(self) -> None:
        """Should use AWS_SMS_OTP_LENGTH setting by default."""
        with patch("apps.sms.services.settings") as mock_settings:
            mock_settings.AWS_SMS_OTP_LENGTH = 4
            code = generate_otp_code()
            assert len(code) == 4


@pytest.mark.django_db
class TestSendPhoneVerificationOTP:
    """Tests for sending phone verification OTP."""

    def test_sends_otp_successfully(self) -> None:
        """Should send OTP and create verification record."""
        user = UserFactory.create()
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}

            otp = send_phone_verification_otp(phone, user)

        assert otp.phone_number == phone
        assert otp.user == user
        assert len(otp.code) == 4  # Default from settings
        assert otp.purpose == OTPVerification.Purpose.PHONE_VERIFY
        assert not otp.is_verified
        assert otp.aws_message_id == "msg-123"
        mock_send.assert_called_once()

    def test_rate_limits_after_3_requests(self) -> None:
        """Should reject more than 3 OTPs per phone per hour."""
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}

            # Send 3 OTPs successfully
            for _ in range(3):
                send_phone_verification_otp(phone)

            # 4th should be rate limited
            with pytest.raises(OTPRateLimitError):
                send_phone_verification_otp(phone)

    def test_invalidates_previous_otps(self) -> None:
        """Should expire previous unused OTPs for same phone/purpose."""
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}

            # Send first OTP
            otp1 = send_phone_verification_otp(phone)
            assert otp1.is_valid

            # Send second OTP
            otp2 = send_phone_verification_otp(phone)

            # First OTP should now be expired
            otp1.refresh_from_db()
            assert otp1.is_expired
            assert otp2.is_valid


@pytest.mark.django_db
class TestVerifyOTP:
    """Tests for OTP verification."""

    def test_verifies_valid_code(self) -> None:
        """Should verify correct OTP code."""
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}
            otp = send_phone_verification_otp(phone)

        verified = verify_otp(phone, otp.code)

        assert verified.is_verified
        assert verified.verified_at is not None

    def test_rejects_invalid_code(self) -> None:
        """Should reject incorrect OTP code."""
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}
            send_phone_verification_otp(phone)

        with pytest.raises(OTPInvalidError):
            verify_otp(phone, "0000")

    def test_increments_attempts_on_failure(self) -> None:
        """Should track failed verification attempts."""
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}
            otp = send_phone_verification_otp(phone)

        # Try wrong code
        with pytest.raises(OTPInvalidError):
            verify_otp(phone, "0000")

        otp.refresh_from_db()
        assert otp.attempts == 1

    def test_rejects_expired_otp(self) -> None:
        """Should reject expired OTP."""
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}
            otp = send_phone_verification_otp(phone)

        # Manually expire the OTP
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()

        with pytest.raises(OTPExpiredError):
            verify_otp(phone, otp.code)

    def test_rejects_after_max_attempts(self) -> None:
        """Should reject after max verification attempts."""
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}
            otp = send_phone_verification_otp(phone)

        # Exhaust attempts
        otp.attempts = otp.max_attempts
        otp.save()

        with pytest.raises(OTPMaxAttemptsError):
            verify_otp(phone, otp.code)

    def test_rejects_when_no_otp_exists(self) -> None:
        """Should reject when no OTP exists for phone."""
        with pytest.raises(OTPInvalidError):
            verify_otp("+14155559999", "1234")


@pytest.mark.django_db
class TestVerifyPhoneForUser:
    """Tests for verify_phone_for_user service."""

    def test_updates_user_phone_verified_at(self) -> None:
        """Should update user's phone_verified_at on success."""
        user = UserFactory.create(phone_number="", phone_verified_at=None)
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}
            otp = send_phone_verification_otp(phone, user)

        updated_user = verify_phone_for_user(user, phone, otp.code)

        assert updated_user.phone_number == phone
        assert updated_user.phone_verified_at is not None

    def test_raises_on_invalid_code(self) -> None:
        """Should raise error on invalid OTP code."""
        user = UserFactory.create()
        phone = "+14155551234"

        with patch("apps.sms.services.send_otp_message") as mock_send:
            mock_send.return_value = {"message_id": "msg-123", "success": True}
            send_phone_verification_otp(phone, user)

        with pytest.raises(OTPInvalidError):
            verify_phone_for_user(user, phone, "0000")


@pytest.mark.django_db
class TestCleanupExpiredOTPs:
    """Tests for expired OTP cleanup."""

    def test_deletes_expired_otps_older_than_24h(self) -> None:
        """Should delete expired OTPs older than 24 hours."""
        phone = "+14155551234"

        # Create an old expired OTP
        old_otp = OTPVerification.objects.create(
            phone_number=phone,
            code="1234",
            expires_at=timezone.now() - timedelta(hours=25),
        )

        # Create a recent expired OTP
        recent_otp = OTPVerification.objects.create(
            phone_number=phone,
            code="5678",
            expires_at=timezone.now() - timedelta(hours=1),
        )

        deleted = cleanup_expired_otps()

        assert deleted == 1
        assert not OTPVerification.objects.filter(id=old_otp.id).exists()
        assert OTPVerification.objects.filter(id=recent_otp.id).exists()
