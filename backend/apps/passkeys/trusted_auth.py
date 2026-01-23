"""
Trusted Auth Token service for Stytch session attestation.

Creates signed JWTs that can be exchanged for Stytch B2B sessions
via the sessions.attest() API. Also provides shared key management utilities.
"""

import time
from functools import lru_cache
from typing import Any

import jwt
from django.conf import settings

# Token expiration: 5 minutes (short-lived for security)
TRUSTED_AUTH_TOKEN_EXPIRY_SECONDS = 300


def get_signing_private_key() -> str:
    """
    Get the RSA private key for JWT signing.

    Handles escaped newlines from environment variables.

    Returns:
        PEM-encoded RSA private key string

    Raises:
        ValueError: If PASSKEY_JWT_PRIVATE_KEY is not configured
    """
    private_key = settings.PASSKEY_JWT_PRIVATE_KEY
    if not private_key:
        raise ValueError("PASSKEY_JWT_PRIVATE_KEY is not configured")

    if "\\n" in private_key:
        private_key = private_key.replace("\\n", "\n")

    return private_key


@lru_cache(maxsize=1)
def get_signing_public_key() -> str:
    """
    Derive public key from private key for JWT verification.

    Cached since key derivation is expensive and key doesn't change.

    Returns:
        PEM-encoded RSA public key string
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key_pem = get_signing_private_key()
    private_key = load_pem_private_key(private_key_pem.encode(), password=None)
    public_key = private_key.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return public_key_pem.decode()


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
        # Required claims for Stytch Trusted Auth
        "token_id": str(user_id),  # Required: unique identifier for the token
        "email": email,  # Required: user's email address
        "iss": settings.STYTCH_TRUSTED_AUTH_ISSUER,  # Standard JWT issuer
        "aud": settings.STYTCH_TRUSTED_AUTH_AUDIENCE,  # Standard JWT audience
        "iat": now,
        "exp": now + TRUSTED_AUTH_TOKEN_EXPIRY_SECONDS,
        # Optional claims that map to Stytch fields (per attribute mapping)
        "org_id": organization_id,  # Maps to organization_id
        "member_id": member_id,  # Maps to external_member_id
    }

    token = jwt.encode(
        payload,
        get_signing_private_key(),
        algorithm="RS256",
        headers={"kid": settings.JWT_SIGNING_KEY_ID},
    )

    return token
