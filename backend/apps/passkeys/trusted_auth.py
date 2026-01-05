"""
Trusted Auth Token service for Stytch session attestation.

Creates signed JWTs that can be exchanged for Stytch B2B sessions
via the sessions.attest() API.
"""

import time
from typing import Any

import jwt
from django.conf import settings


def create_trusted_auth_token(
    email: str,
    member_id: str,
    organization_id: str,
    user_id: int,
) -> str:
    """
    Create a signed JWT for Stytch session attestation.

    This token can be exchanged for a real Stytch B2B session using
    the sessions.attest() API.

    Args:
        email: User's email address
        member_id: Stytch member ID
        organization_id: Stytch organization ID
        user_id: Local user ID

    Returns:
        Signed JWT string
    """
    now = int(time.time())

    payload: dict[str, Any] = {
        # Required claims for Stytch
        "sub": str(user_id),  # Maps to token_id
        "email": email,  # Maps to email
        "iss": settings.STYTCH_TRUSTED_AUTH_ISSUER,
        "aud": settings.STYTCH_TRUSTED_AUTH_AUDIENCE,
        "iat": now,
        "exp": now + 300,  # 5 minute expiry (short-lived)
        # Custom claims for context
        "stytch_member_id": member_id,
        "stytch_org_id": organization_id,
    }

    # Sign with RS256 using our private key
    private_key = settings.PASSKEY_JWT_PRIVATE_KEY
    if not private_key:
        raise ValueError("PASSKEY_JWT_PRIVATE_KEY is not configured")

    # Handle escaped newlines from environment variables
    # If the key contains literal \n characters, replace them with actual newlines
    if "\\n" in private_key:
        private_key = private_key.replace("\\n", "\n")

    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "passkey-auth-key-1"},
    )

    return token
