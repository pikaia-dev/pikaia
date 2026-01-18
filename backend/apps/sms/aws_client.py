"""
AWS End User Messaging SMS client wrapper.

Uses boto3 pinpoint-sms-voice-v2 API to send SMS messages.
"""

import logging
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


class SMSError(Exception):
    """Exception raised when SMS sending fails."""

    pass


@lru_cache(maxsize=1)
def get_sms_client() -> Any:
    """
    Get AWS SMS client (pinpoint-sms-voice-v2).

    Uses lru_cache to reuse the client instance.
    Credentials are loaded from environment (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    or IAM role when running on AWS.
    """
    return boto3.client(
        "pinpoint-sms-voice-v2",
        region_name=settings.AWS_SMS_REGION,
    )


def send_sms(phone_number: str, message: str) -> dict[str, Any]:
    """
    Send an SMS message to a phone number.

    Args:
        phone_number: E.164 format phone number (e.g., +14155551234)
        message: The message body to send

    Returns:
        Dict with message_id and other response data

    Raises:
        SMSError: If sending fails
    """
    if not settings.AWS_SMS_ORIGINATION_IDENTITY:
        logger.error("AWS_SMS_ORIGINATION_IDENTITY not configured")
        raise SMSError("SMS service not configured")

    client = get_sms_client()

    try:
        response = client.send_text_message(
            DestinationPhoneNumber=phone_number,
            OriginationIdentity=settings.AWS_SMS_ORIGINATION_IDENTITY,
            MessageBody=message,
            MessageType="TRANSACTIONAL",
        )

        logger.info(
            "SMS sent successfully to %s (message_id: %s)",
            phone_number[-4:],  # Log only last 4 digits for privacy
            response.get("MessageId"),
        )

        return {
            "message_id": response.get("MessageId"),
            "success": True,
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))
        logger.error("AWS SMS ClientError: %s - %s", error_code, error_message)
        raise SMSError(f"Failed to send SMS: {error_message}") from e

    except BotoCoreError as e:
        logger.error("AWS SMS BotoCoreError: %s", str(e))
        raise SMSError(f"SMS service error: {str(e)}") from e


def send_otp_message(
    phone_number: str, otp_code: str, app_name: str = "Pikaia"
) -> dict[str, Any]:
    """
    Send an OTP verification message.

    Args:
        phone_number: E.164 format phone number
        otp_code: The OTP code to send
        app_name: App name for the message

    Returns:
        Dict with message_id and success status
    """
    message = f"Your {app_name} verification code is: {otp_code}"
    return send_sms(phone_number, message)
