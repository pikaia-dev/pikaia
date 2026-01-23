"""
Device linking services.

Handles QR code token generation, device linking, and session management.
"""

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import jwt
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Member, User
from apps.accounts.stytch_client import get_stytch_client
from apps.core.logging import get_logger
from apps.devices.constants import JWTAction
from apps.devices.exceptions import (
    DeviceAlreadyLinkedError,
    RateLimitError,
    TokenExpiredError,
    TokenInvalidError,
    TokenUsedError,
)
from apps.devices.models import Device, DeviceLinkToken
from apps.organizations.models import Organization
from apps.passkeys.trusted_auth import (
    create_trusted_auth_token,
    get_signing_private_key,
    get_signing_public_key,
)

logger = get_logger(__name__)


@dataclass
class LinkTokenResult:
    """Result of creating a link token."""

    qr_url: str
    expires_at: datetime
    token_record: DeviceLinkToken


@dataclass
class LinkCompleteResult:
    """Result of completing device linking."""

    device: Device
    session_token: str
    session_jwt: str
    session_expires_at: datetime
    member_id: str
    organization_id: str


def _hash_token(token: str) -> str:
    """Create SHA-256 hash of token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_link_token(
    user: User,
    member: Member,
    organization: Organization,
) -> LinkTokenResult:
    """
    Generate a QR code link token for device linking.

    Creates a signed JWT containing user/member/org info that the mobile
    app can scan to complete device linking.

    Args:
        user: User initiating the link
        member: Member context for the link
        organization: Organization context

    Returns:
        LinkTokenResult with QR URL and token record

    Raises:
        RateLimitError: If user has exceeded link attempts
    """
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_attempts = DeviceLinkToken.objects.filter(
        user=user,
        created_at__gte=one_hour_ago,
    ).count()

    max_attempts: int = settings.DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR
    if recent_attempts >= max_attempts:
        logger.warning(
            "device_link_rate_limit",
            user_id=user.id,
            attempts=recent_attempts,
        )
        raise RateLimitError(f"Too many link attempts. Maximum {max_attempts} per hour.")

    now = int(time.time())
    token_expiry_seconds: int = settings.DEVICE_LINK_TOKEN_EXPIRY_SECONDS
    expires_at = timezone.now() + timedelta(seconds=token_expiry_seconds)

    payload: dict[str, Any] = {
        "jti": str(timezone.now().timestamp()),
        "iat": now,
        "exp": now + token_expiry_seconds,
        "sub": str(user.id),
        "action": JWTAction.DEVICE_LINK,
        "email": user.email,
        "org_id": organization.stytch_org_id,
        "member_id": member.stytch_member_id,
    }

    token = jwt.encode(
        payload,
        get_signing_private_key(),
        algorithm="RS256",
        headers={"kid": settings.JWT_SIGNING_KEY_ID},
    )

    token_hash = _hash_token(token)

    token_record = DeviceLinkToken.objects.create(
        user=user,
        member=member,
        organization=organization,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    qr_url = f"{settings.DEVICE_LINK_URL_SCHEME}?token={token}"

    logger.info(
        "device_link_token_created",
        user_id=user.id,
        token_id=str(token_record.id),
        expires_at=expires_at.isoformat(),
    )

    return LinkTokenResult(
        qr_url=qr_url,
        expires_at=expires_at,
        token_record=token_record,
    )


def complete_device_link(
    token: str,
    device_uuid: str,
    name: str,
    platform: str,
    os_version: str = "",
    app_version: str = "",
) -> LinkCompleteResult:
    """
    Complete device linking using the QR code token.

    Validates the token, creates a Device record, and returns a
    Stytch session for the mobile app.

    Args:
        token: JWT token from QR code
        device_uuid: Unique device identifier
        name: Device name
        platform: Platform (ios, android)
        os_version: OS version
        app_version: App version

    Returns:
        LinkCompleteResult with device and session info

    Raises:
        TokenExpiredError: Token has expired
        TokenUsedError: Token already used
        TokenInvalidError: Token is invalid
        DeviceAlreadyLinkedError: Device already linked to another user
    """
    try:
        public_key = get_signing_public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"require": ["exp", "sub", "action"]},
        )
    except jwt.ExpiredSignatureError:
        logger.warning("device_link_token_expired")
        raise TokenExpiredError("Link token has expired. Please generate a new QR code.") from None
    except jwt.InvalidTokenError as e:
        logger.warning("device_link_token_invalid", error=str(e))
        raise TokenInvalidError("Invalid link token.") from None

    if payload.get("action") != JWTAction.DEVICE_LINK:
        raise TokenInvalidError("Invalid token type.")

    token_hash = _hash_token(token)
    try:
        token_record = DeviceLinkToken.objects.select_related("user", "member", "organization").get(
            token_hash=token_hash
        )
    except DeviceLinkToken.DoesNotExist:
        raise TokenInvalidError("Link token not found.") from None

    if token_record.is_used:
        raise TokenUsedError("Link token has already been used.")

    if token_record.is_expired:
        raise TokenExpiredError("Link token has expired. Please generate a new QR code.")

    user = token_record.user
    member = token_record.member
    organization = token_record.organization

    existing_device = Device.all_objects.filter(device_uuid=device_uuid).first()
    if existing_device and existing_device.user_id != user.id and not existing_device.is_revoked:
        raise DeviceAlreadyLinkedError("This device is already linked to another account.")

    with transaction.atomic():
        token_record.mark_used()

        if existing_device and existing_device.user_id == user.id:
            device = existing_device
            device.name = name
            device.platform = platform
            device.os_version = os_version
            device.app_version = app_version
            device.revoked_at = None
            device.save(
                update_fields=[
                    "name",
                    "platform",
                    "os_version",
                    "app_version",
                    "revoked_at",
                    "updated_at",
                ]
            )
        elif existing_device and existing_device.is_revoked:
            device = existing_device
            device.user = user
            device.name = name
            device.platform = platform
            device.os_version = os_version
            device.app_version = app_version
            device.revoked_at = None
            device.save()
        else:
            try:
                device = Device.objects.create(
                    user=user,
                    device_uuid=device_uuid,
                    name=name,
                    platform=platform,
                    os_version=os_version,
                    app_version=app_version,
                )
            except IntegrityError:
                device = Device.objects.get(device_uuid=device_uuid)
                if device.user_id != user.id:
                    raise DeviceAlreadyLinkedError(
                        "This device is already linked to another account."
                    ) from None

    session_token, session_jwt, session_expires_at = _create_mobile_session(
        user, member, organization
    )

    logger.info(
        "device_link_completed",
        user_id=user.id,
        device_id=device.id,
        device_uuid=device_uuid,
        platform=platform,
    )

    return LinkCompleteResult(
        device=device,
        session_token=session_token,
        session_jwt=session_jwt,
        session_expires_at=session_expires_at,
        member_id=member.stytch_member_id,
        organization_id=organization.stytch_org_id,
    )


def _create_mobile_session(
    user: User,
    member: Member,
    organization: Organization,
) -> tuple[str, str, datetime]:
    """
    Create a Stytch session for the mobile app using trusted auth.

    Returns:
        Tuple of (session_token, session_jwt, session_expires_at)
    """
    trusted_token = create_trusted_auth_token(
        email=user.email,
        member_id=member.stytch_member_id,
        organization_id=organization.stytch_org_id,
        user_id=user.id,
    )

    client = get_stytch_client()
    response = client.sessions.attest(
        profile_id=settings.STYTCH_TRUSTED_AUTH_PROFILE_ID,
        token=trusted_token,
        organization_id=organization.stytch_org_id,
        session_duration_minutes=settings.DEVICE_SESSION_EXPIRY_MINUTES,
    )

    # Calculate session expiry time
    session_expires_at = timezone.now() + timedelta(minutes=settings.DEVICE_SESSION_EXPIRY_MINUTES)

    return response.session_token, response.session_jwt, session_expires_at


def revoke_device(device_id: int, user: User) -> None:
    """
    Revoke a device, preventing it from syncing.

    Args:
        device_id: ID of the device to revoke
        user: User who owns the device (for authorization)

    Raises:
        Device.DoesNotExist: If device not found or not owned by user
    """
    device = Device.objects.get(id=device_id, user=user)
    device.revoke()

    logger.info(
        "device_revoked",
        user_id=user.id,
        device_id=device_id,
    )


def list_user_devices(user: User) -> list[Device]:
    """
    List all active devices for a user.

    Args:
        user: User to list devices for

    Returns:
        List of active (non-revoked) devices
    """
    return list(Device.objects.filter(user=user).order_by("-created_at"))
