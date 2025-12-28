"""
Auth API endpoints.

Handles Stytch B2B authentication flows:
- Magic link send/authenticate
- Discovery org creation/exchange
- Session management
"""

import logging

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from stytch.core.response_base import StytchError

from apps.accounts.schemas import (
    DiscoveredOrganization,
    DiscoveryCreateOrgRequest,
    DiscoveryExchangeRequest,
    MagicLinkAuthenticateRequest,
    MagicLinkAuthenticateResponse,
    MagicLinkSendRequest,
    MemberInfo,
    MeResponse,
    MessageResponse,
    OrganizationInfo,
    SessionResponse,
    UserInfo,
)
from apps.accounts.services import sync_session_to_local
from apps.accounts.stytch_client import get_stytch_client
from apps.core.schemas import ErrorResponse

logger = logging.getLogger(__name__)

router = Router(tags=["auth"])


@router.post(
    "/magic-link/send",
    response={200: MessageResponse, 400: ErrorResponse},
    operation_id="sendMagicLink",
    summary="Send magic link email",
)
def send_magic_link(request: HttpRequest, payload: MagicLinkSendRequest) -> MessageResponse:
    """
    Send a magic link email for discovery authentication.

    Uses discovery flow - user authenticates first, then picks/creates org.
    """
    client = get_stytch_client()

    try:
        client.magic_links.email.discovery.send(
            email_address=payload.email,
        )
    except StytchError as e:
        logger.warning("Failed to send magic link: %s", e.details.error_message)
        raise HttpError(400, "Failed to send magic link. Please check the email address.") from e

    return MessageResponse(message="Magic link sent. Check your email.")


@router.post(
    "/magic-link/authenticate",
    response={200: MagicLinkAuthenticateResponse, 400: ErrorResponse},
    operation_id="authenticateMagicLink",
    summary="Authenticate magic link token",
)
def authenticate_magic_link(
    request: HttpRequest,
    payload: MagicLinkAuthenticateRequest,
) -> MagicLinkAuthenticateResponse:
    """
    Authenticate a magic link token.

    Returns an intermediate session token (IST) and list of
    organizations the user can join or create.
    """
    client = get_stytch_client()

    try:
        response = client.magic_links.discovery.authenticate(
            discovery_magic_links_token=payload.token,
        )
    except StytchError as e:
        logger.warning("Magic link authentication failed: %s", e.details.error_message)
        raise HttpError(400, "Invalid or expired token.") from e

    # Build list of discovered organizations
    discovered_orgs = [
        DiscoveredOrganization(
            organization_id=org.organization.organization_id,
            organization_name=org.organization.organization_name,
            organization_slug=org.organization.organization_slug,
        )
        for org in response.discovered_organizations
    ]

    return MagicLinkAuthenticateResponse(
        intermediate_session_token=response.intermediate_session_token,
        email=response.email_address,
        discovered_organizations=discovered_orgs,
    )


@router.post(
    "/discovery/create-org",
    response={200: SessionResponse, 400: ErrorResponse, 409: ErrorResponse},
    operation_id="createOrganization",
    summary="Create new organization",
)
def create_organization(
    request: HttpRequest,
    payload: DiscoveryCreateOrgRequest,
) -> SessionResponse:
    """
    Create a new organization from discovery flow.

    Exchanges the IST for a session and creates the org.
    """
    client = get_stytch_client()

    try:
        response = client.discovery.organizations.create(
            intermediate_session_token=payload.intermediate_session_token,
            organization_name=payload.organization_name,
            organization_slug=payload.organization_slug,
        )
    except StytchError as e:
        error_msg = e.details.error_message.lower() if e.details.error_message else ""
        if "slug" in error_msg or "duplicate" in error_msg:
            logger.warning("Organization slug conflict: %s", e.details.error_message)
            raise HttpError(409, "Organization slug already in use. Try a different one.") from e
        logger.warning("Failed to create organization: %s", e.details.error_message)
        raise HttpError(400, "Failed to create organization.") from e

    # Sync to local database
    user, member, org = sync_session_to_local(
        stytch_member=response.member,
        stytch_organization=response.organization,
    )

    return SessionResponse(
        session_token=response.session_token,
        session_jwt=response.session_jwt,
        member_id=response.member.member_id,
        organization_id=response.organization.organization_id,
    )


@router.post(
    "/discovery/exchange",
    response={200: SessionResponse, 400: ErrorResponse},
    operation_id="exchangeSession",
    summary="Exchange IST for session",
)
def exchange_session(
    request: HttpRequest,
    payload: DiscoveryExchangeRequest,
) -> SessionResponse:
    """
    Exchange IST for session by joining an existing organization.
    """
    client = get_stytch_client()

    try:
        response = client.discovery.intermediate_sessions.exchange(
            intermediate_session_token=payload.intermediate_session_token,
            organization_id=payload.organization_id,
        )
    except StytchError as e:
        logger.warning("Failed to join organization: %s", e.details.error_message)
        raise HttpError(400, "Failed to join organization.") from e

    # Sync to local database
    user, member, org = sync_session_to_local(
        stytch_member=response.member,
        stytch_organization=response.organization,
    )

    return SessionResponse(
        session_token=response.session_token,
        session_jwt=response.session_jwt,
        member_id=response.member.member_id,
        organization_id=response.organization.organization_id,
    )


@router.post(
    "/logout",
    response={200: MessageResponse, 401: ErrorResponse},
    operation_id="logout",
    summary="Revoke current session",
)
def logout(request: HttpRequest) -> MessageResponse:
    """
    Revoke the current session.

    Expects session JWT in Authorization header (Bearer <session_jwt>),
    consistent with other authenticated endpoints.
    """
    # Get session JWT from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HttpError(401, "No session provided")

    session_jwt = auth_header.replace("Bearer ", "")
    client = get_stytch_client()

    try:
        # Authenticate the JWT to get the member_session_id
        response = client.sessions.authenticate_jwt(session_jwt=session_jwt)
        # Revoke using member_session_id (from the authenticated session)
        client.sessions.revoke(member_session_id=response.member_session.member_session_id)
    except StytchError:
        # Session already invalid/expired - still return success
        pass

    return MessageResponse(message="Logged out successfully")


@router.get(
    "/me",
    response={200: MeResponse, 401: ErrorResponse},
    operation_id="getCurrentUser",
    summary="Get current user info",
)
def get_current_user(request: HttpRequest) -> MeResponse:
    """
    Get current authenticated user, member, and organization info.

    Requires valid session JWT in Authorization header.
    """
    # These are set by the auth middleware
    if not hasattr(request, "auth_user") or request.auth_user is None:  # type: ignore[attr-defined]
        raise HttpError(401, "Not authenticated")

    user = request.auth_user  # type: ignore[attr-defined]
    member = request.auth_member  # type: ignore[attr-defined]
    org = request.auth_organization  # type: ignore[attr-defined]

    return MeResponse(
        user=UserInfo(
            id=user.id,
            email=user.email,
            name=user.name,
        ),
        member=MemberInfo(
            id=member.id,
            stytch_member_id=member.stytch_member_id,
            role=member.role,
            is_admin=member.is_admin,
        ),
        organization=OrganizationInfo(
            id=org.id,
            stytch_org_id=org.stytch_org_id,
            name=org.name,
            slug=org.slug,
        ),
    )
