"""
OTP generation and verification services.
"""

import hashlib
import re
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.logging import get_logger
from apps.core.throttling import RateLimitExceeded, increment_rate_limit, peek_rate_limit
from apps.sms.aws_client import SMSError, send_otp_message
from apps.sms.models import OTPVerification

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = get_logger(__name__)


class OTPError(Exception):
    """Base exception for OTP operations."""

    pass


class OTPRateLimitError(OTPError):
    """Raised when rate limit is exceeded."""

    pass


class OTPExpiredError(OTPError):
    """Raised when OTP has expired."""

    pass


class OTPInvalidError(OTPError):
    """Raised when OTP code is invalid."""

    pass


class OTPMaxAttemptsError(OTPError):
    """Raised when max verification attempts exceeded."""

    pass


_E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_e164_phone_number(phone_number: str) -> str:
    """Validate and normalize a phone number to E.164 format.

    Returns the stripped phone number on success, raises OTPInvalidError otherwise.
    """
    phone_number = phone_number.strip()
    if not _E164_PATTERN.match(phone_number):
        raise OTPInvalidError(f"Invalid E.164 phone number: {phone_number}")
    return phone_number


def hash_otp_code(code: str) -> str:
    """Hash an OTP code using SHA-256 for secure storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def generate_otp_code(length: int | None = None) -> str:
    """
    Generate a cryptographically secure OTP code.

    Args:
        length: Number of digits (defaults to AWS_SMS_OTP_LENGTH)

    Returns:
        String of random digits
    """
    if length is None:
        length = settings.AWS_SMS_OTP_LENGTH

    # Generate random digits using secrets for cryptographic security
    return "".join(secrets.choice("0123456789") for _ in range(length))


def send_phone_verification_otp(
    phone_number: str,
    user: "User | None" = None,
    purpose: str = OTPVerification.Purpose.PHONE_VERIFY,
) -> OTPVerification:
    """
    Generate and send an OTP for phone verification.

    Implements rate limiting: max 3 OTPs per phone number per hour.

    Args:
        phone_number: E.164 format phone number
        user: Optional user requesting verification
        purpose: Purpose of the OTP (phone_verify or login)

    Returns:
        The created OTPVerification instance

    Raises:
        OTPRateLimitError: If rate limit exceeded
        SMSError: If SMS sending fails
    """
    phone_number = validate_e164_phone_number(phone_number)

    # Rate limiting: max 3 OTPs per phone per hour
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_otps = OTPVerification.objects.filter(
        phone_number=phone_number,
        created_at__gte=one_hour_ago,
    ).count()

    if recent_otps >= 3:
        logger.warning("OTP rate limit exceeded for phone %s", phone_number[-4:])
        raise OTPRateLimitError("Too many verification attempts. Please try again later.")

    # Generate new OTP code before entering the transaction
    code = generate_otp_code()

    # Atomically invalidate existing OTPs and create the new one to prevent
    # a race condition where concurrent requests produce two valid OTPs.
    with transaction.atomic():
        OTPVerification.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_verified=False,
        ).update(expires_at=timezone.now())

        otp = OTPVerification.objects.create(
            user=user,
            phone_number=phone_number,
            code_hash=hash_otp_code(code),
            purpose=purpose,
        )

    # Send SMS outside the transaction to avoid holding DB locks during
    # an external API call. If sending fails, delete the OTP record so it
    # does not consume a rate-limit slot for a code the user never received.
    try:
        result = send_otp_message(phone_number, code)
        aws_message_id = result.get("message_id", "")
    except SMSError:
        otp.delete()
        raise

    # Persist the AWS message ID for audit/debugging purposes
    otp.aws_message_id = aws_message_id
    otp.save(update_fields=["aws_message_id"])

    logger.info(
        "OTP sent to %s (purpose: %s, otp_id: %s)",
        phone_number[-4:],
        purpose,
        otp.id,
    )

    return otp


def verify_otp(
    phone_number: str,
    code: str,
    purpose: str = OTPVerification.Purpose.PHONE_VERIFY,
) -> OTPVerification:
    """
    Verify an OTP code.

    Args:
        phone_number: E.164 format phone number
        code: The OTP code to verify
        purpose: Purpose of the OTP

    Returns:
        The verified OTPVerification instance

    Raises:
        OTPInvalidError: If code doesn't match or no valid OTP exists
        OTPExpiredError: If OTP has expired
        OTPMaxAttemptsError: If max attempts exceeded
    """
    phone_number = validate_e164_phone_number(phone_number)
    code = code.strip()

    rate_limit_key = f"otp_verify:{phone_number}"
    rate_limit_window = 900  # 15 minutes

    # Check rate limit (without incrementing -- only failures count)
    try:
        peek_rate_limit(
            rate_limit_key,
            max_requests=10,
            window_seconds=rate_limit_window,
        )
    except RateLimitExceeded:
        logger.warning("OTP verify rate limit exceeded for phone %s", phone_number[-4:])
        raise OTPRateLimitError("Too many verification attempts. Please try again later.") from None

    # Find the most recent unverified OTP for this phone/purpose
    otp = (
        OTPVerification.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_verified=False,
        )
        .order_by("-created_at")
        .first()
    )

    if not otp:
        increment_rate_limit(rate_limit_key, window_seconds=rate_limit_window)
        logger.warning("No OTP found for phone %s", phone_number[-4:])
        raise OTPInvalidError("Invalid verification code")

    # Check if expired
    if otp.is_expired:
        increment_rate_limit(rate_limit_key, window_seconds=rate_limit_window)
        logger.info("OTP expired for phone %s", phone_number[-4:])
        raise OTPExpiredError("Verification code has expired. Please request a new one.")

    # Check attempts
    if otp.attempts >= otp.max_attempts:
        increment_rate_limit(rate_limit_key, window_seconds=rate_limit_window)
        logger.warning("Max OTP attempts exceeded for phone %s", phone_number[-4:])
        raise OTPMaxAttemptsError("Too many incorrect attempts. Please request a new code.")

    # Verify code (constant-time comparison to prevent timing attacks)
    if not secrets.compare_digest(otp.code_hash, hash_otp_code(code)):
        otp.increment_attempts()
        increment_rate_limit(rate_limit_key, window_seconds=rate_limit_window)
        remaining = otp.max_attempts - otp.attempts
        logger.info(
            "Invalid OTP attempt for phone %s (%d attempts remaining)",
            phone_number[-4:],
            remaining,
        )
        raise OTPInvalidError(f"Invalid verification code. {remaining} attempts remaining.")

    # Success -- no rate limit increment for legitimate verifications
    otp.mark_verified()

    logger.info(
        "OTP verified successfully for phone %s (otp_id: %s)",
        phone_number[-4:],
        otp.id,
    )

    return otp


@transaction.atomic
def verify_phone_for_user(user: "User", phone_number: str, code: str) -> "User":
    """
    Verify phone OTP and update user's phone_verified_at.

    Args:
        user: The user to update
        phone_number: E.164 format phone number
        code: The OTP code

    Returns:
        Updated user instance

    Raises:
        OTPError subclass on verification failure
    """
    # Verify the OTP
    verify_otp(phone_number, code, OTPVerification.Purpose.PHONE_VERIFY)

    # Update user's phone
    user.phone_number = phone_number
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_number", "phone_verified_at", "updated_at"])

    logger.info("Phone verified for user %s", user.email)

    return user


def cleanup_expired_otps() -> int:
    """
    Delete expired OTP records older than 24 hours.

    Intended to be called from a scheduled task.

    Returns:
        Number of records deleted
    """
    cutoff = timezone.now() - timedelta(hours=24)
    deleted, _ = OTPVerification.objects.filter(
        expires_at__lt=cutoff,
    ).delete()

    if deleted:
        logger.info("Cleaned up %d expired OTP records", deleted)

    return deleted
