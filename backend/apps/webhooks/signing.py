"""
Webhook signature generation and verification.

Implements HMAC-SHA256 signing with timestamp to prevent replay attacks.
"""

import hashlib
import hmac
import time

# Clock skew tolerance in seconds (5 minutes)
CLOCK_SKEW_TOLERANCE = 300

# Signature version prefix
SIGNATURE_VERSION = "v1"


def generate_signature(payload: str, secret: str, timestamp: int | None = None) -> tuple[str, int]:
    """
    Generate a webhook signature for the given payload.

    Args:
        payload: The JSON payload string to sign
        secret: The webhook signing secret
        timestamp: Unix timestamp (defaults to current time)

    Returns:
        Tuple of (signature, timestamp) where signature is "v1=<hex>"
    """
    if timestamp is None:
        timestamp = int(time.time())

    # Construct the signed payload: "timestamp.payload"
    signed_payload = f"{timestamp}.{payload}"

    # Compute HMAC-SHA256
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{SIGNATURE_VERSION}={signature}", timestamp


def verify_signature(
    payload: str,
    secret: str,
    signature: str,
    timestamp: int,
    tolerance: int = CLOCK_SKEW_TOLERANCE,
) -> bool:
    """
    Verify a webhook signature.

    Args:
        payload: The JSON payload string
        secret: The webhook signing secret
        signature: The signature from X-Webhook-Signature header
        timestamp: The timestamp from X-Webhook-Timestamp header
        tolerance: Maximum allowed clock skew in seconds

    Returns:
        True if signature is valid and within time tolerance
    """
    # Check clock skew
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance:
        return False

    # Generate expected signature
    expected_signature, _ = generate_signature(payload, secret, timestamp)

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, signature)


def generate_headers(payload: str, secret: str, event_id: str) -> dict[str, str]:
    """
    Generate all webhook headers for a request.

    Args:
        payload: The JSON payload string
        secret: The webhook signing secret
        event_id: The unique event ID

    Returns:
        Dict of headers to include in the webhook request
    """
    signature, timestamp = generate_signature(payload, secret)

    return {
        "Content-Type": "application/json",
        "X-Webhook-ID": event_id,
        "X-Webhook-Timestamp": str(timestamp),
        "X-Webhook-Signature": signature,
        "User-Agent": "Tango-Webhooks/1.0",
    }
