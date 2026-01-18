"""
API endpoints for SMS/OTP verification.
"""

import logging

from django.conf import settings
from ninja import Router
from ninja.errors import HttpError

from apps.core.schemas import ErrorResponse
from apps.core.security import BearerAuth
from apps.core.types import AuthenticatedHttpRequest
from apps.events.services import publish_event
from apps.sms.aws_client import SMSError
from apps.sms.schemas import (
    SendOTPRequest,
    SendOTPResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from apps.sms.services import (
    OTPError,
    OTPExpiredError,
    OTPInvalidError,
    OTPMaxAttemptsError,
    OTPRateLimitError,
    send_phone_verification_otp,
    verify_phone_for_user,
)

logger = logging.getLogger(__name__)

router = Router(tags=["Phone Verification"])
bearer_auth = BearerAuth()


@router.post(
    "/send",
    response={200: SendOTPResponse, 400: ErrorResponse, 401: ErrorResponse, 429: ErrorResponse},
    auth=bearer_auth,
    operation_id="sendPhoneVerificationOTP",
    summary="Send phone verification OTP",
)
def send_verification_otp(
    request: AuthenticatedHttpRequest,
    payload: SendOTPRequest,
) -> SendOTPResponse:
    """
    Send a one-time password (OTP) to verify a phone number.

    The OTP expires after the configured time (default: 30 minutes).
    Rate limited to 3 requests per phone number per hour.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    user = request.auth_user

    try:
        send_phone_verification_otp(
            phone_number=payload.phone_number,
            user=user,
        )
    except OTPRateLimitError as e:
        raise HttpError(429, str(e)) from None
    except SMSError as e:
        logger.error("Failed to send OTP SMS: %s", str(e))
        raise HttpError(400, "Failed to send verification code. Please try again.") from None

    return SendOTPResponse(
        success=True,
        message=f"Verification code sent to {payload.phone_number}",
        expires_in_minutes=settings.AWS_SMS_OTP_EXPIRY_MINUTES,
    )


@router.post(
    "/verify",
    response={200: VerifyOTPResponse, 400: ErrorResponse, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="verifyPhoneOTP",
    summary="Verify phone OTP and update profile",
)
def verify_phone_otp(
    request: AuthenticatedHttpRequest,
    payload: VerifyOTPRequest,
) -> VerifyOTPResponse:
    """
    Verify an OTP code and mark the phone as verified.

    On success, updates the user's phone_number and sets phone_verified_at.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    user = request.auth_user
    org = request.auth_organization

    try:
        verify_phone_for_user(
            user=user,
            phone_number=payload.phone_number,
            code=payload.code,
        )
    except OTPExpiredError as e:
        raise HttpError(400, str(e)) from None
    except OTPMaxAttemptsError as e:
        raise HttpError(400, str(e)) from None
    except OTPInvalidError as e:
        raise HttpError(400, str(e)) from None
    except OTPError as e:
        logger.error("OTP verification error: %s", str(e))
        raise HttpError(400, "Verification failed. Please try again.") from None

    # Emit phone verified event
    publish_event(
        event_type="user.phone_verified",
        aggregate=user,
        data={
            "phone_number": payload.phone_number,
        },
        actor=user,
        organization_id=str(org.id) if org else None,
    )

    return VerifyOTPResponse(
        success=True,
        message="Phone number verified successfully",
        phone_verified=True,
    )
