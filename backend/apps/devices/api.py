"""
Device API endpoints.

Provides endpoints for device linking and management.
"""

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.core.security import BearerAuth, get_auth_context
from apps.devices.exceptions import (
    DeviceAlreadyLinkedError,
    RateLimitError,
    TokenExpiredError,
    TokenInvalidError,
    TokenUsedError,
)
from apps.devices.models import Device
from apps.devices.schemas import (
    CompleteLinkRequest,
    CompleteLinkResponse,
    DeviceListResponse,
    DeviceResponse,
    InitiateLinkResponse,
)
from apps.devices.services import (
    complete_device_link,
    create_link_token,
    list_user_devices,
    revoke_device,
)

router = Router(tags=["devices"])
bearer_auth = BearerAuth()


@router.post(
    "/link/initiate",
    response=InitiateLinkResponse,
    auth=bearer_auth,
    summary="Initiate device linking",
    description="Generate QR code data for linking a mobile device. Requires authentication.",
)
def initiate_link(request: HttpRequest) -> InitiateLinkResponse:
    """Generate QR code data for device linking."""
    user, member, organization = get_auth_context(request)

    try:
        result = create_link_token(user=user, member=member, organization=organization)
    except RateLimitError as e:
        raise HttpError(429, str(e)) from None

    expires_in_seconds = int((result.expires_at - result.token_record.created_at).total_seconds())

    return InitiateLinkResponse(
        qr_url=result.qr_url,
        expires_at=result.expires_at,
        expires_in_seconds=expires_in_seconds,
    )


@router.post(
    "/link/complete",
    response=CompleteLinkResponse,
    summary="Complete device linking",
    description="Complete device linking using the QR code token. Called by mobile app.",
)
def complete_link(
    request: HttpRequest,
    payload: CompleteLinkRequest,
) -> CompleteLinkResponse:
    """Complete device linking with QR code token."""
    try:
        result = complete_device_link(
            token=payload.token,
            device_uuid=payload.device_uuid,
            name=payload.name,
            platform=payload.platform,
            os_version=payload.os_version,
            app_version=payload.app_version,
        )
    except TokenExpiredError as e:
        raise HttpError(410, str(e)) from None
    except TokenUsedError as e:
        raise HttpError(409, str(e)) from None
    except TokenInvalidError as e:
        raise HttpError(400, str(e)) from None
    except DeviceAlreadyLinkedError as e:
        raise HttpError(409, str(e)) from None

    return CompleteLinkResponse(
        session_token=result.session_token,
        session_jwt=result.session_jwt,
        session_expires_at=result.session_expires_at,
        device_id=result.device.id,
        user_id=result.device.user_id,
        member_id=result.member_id,
        organization_id=result.organization_id,
    )


@router.get(
    "/",
    response=DeviceListResponse,
    auth=bearer_auth,
    summary="List linked devices",
    description="Get all linked devices for the authenticated user.",
)
def list_devices(request: HttpRequest) -> DeviceListResponse:
    """List all linked devices for the authenticated user."""
    user, _, _ = get_auth_context(request)

    devices = list_user_devices(user)

    return DeviceListResponse(
        devices=[
            DeviceResponse(
                id=d.id,
                name=d.name,
                platform=d.platform,
                os_version=d.os_version,
                app_version=d.app_version,
                created_at=d.created_at,
            )
            for d in devices
        ],
        count=len(devices),
    )


@router.delete(
    "/{device_id}",
    response={204: None},
    auth=bearer_auth,
    summary="Revoke a device",
    description="Revoke a linked device, preventing it from syncing.",
)
def delete_device(request: HttpRequest, device_id: int):
    """Revoke a device owned by the authenticated user."""
    user, _, _ = get_auth_context(request)

    try:
        revoke_device(device_id=device_id, user=user)
    except Device.DoesNotExist:
        raise HttpError(404, "Device not found") from None

    return 204, None
