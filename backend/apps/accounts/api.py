"""
Auth API endpoints.

Handles Stytch B2B authentication flows:
- Magic link send/authenticate
- Discovery org creation/exchange
- Session management
- User profile and organization settings
"""

import contextlib

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from stytch.core.response_base import StytchError

from apps.accounts.models import Member
from apps.accounts.schemas import (
    BillingAddressSchema,
    BillingInfoResponse,
    BulkInviteRequest,
    BulkInviteResponse,
    BulkInviteResultItem,
    DirectoryUserSchema,
    DiscoveredOrganization,
    DiscoveryCreateOrgRequest,
    DiscoveryExchangeRequest,
    EmailUpdateResponse,
    InviteMemberRequest,
    InviteMemberResponse,
    MagicLinkAuthenticateRequest,
    MagicLinkAuthenticateResponse,
    MagicLinkSendRequest,
    MemberInfo,
    MemberListItem,
    MemberListResponse,
    MeResponse,
    MessageResponse,
    MobileProvisionRequest,
    OrganizationDetailResponse,
    OrganizationInfo,
    PhoneOtpResponse,
    SendPhoneOtpRequest,
    SessionResponse,
    StartEmailUpdateRequest,
    UpdateBillingRequest,
    UpdateMemberRoleRequest,
    UpdateOrganizationRequest,
    UpdateProfileRequest,
    UserInfo,
    VerifyPhoneOtpRequest,
)
from apps.accounts.services import (
    bulk_invite_members,
    invite_member,
    list_organization_members,
    provision_mobile_user,
    soft_delete_member,
    sync_session_to_local,
    update_member_role,
)
from apps.accounts.stytch_client import get_stytch_client
from apps.billing.services import sync_billing_to_stripe
from apps.core.logging import get_logger
from apps.core.schemas import ErrorResponse
from apps.core.security import BearerAuth, require_admin
from apps.core.types import AuthenticatedHttpRequest
from apps.events.services import publish_event

logger = get_logger(__name__)

router = Router(tags=["auth"])
bearer_auth = BearerAuth()


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
        if "name" in error_msg and (
            "use" in error_msg or "exist" in error_msg or "taken" in error_msg
        ):
            logger.warning("Organization name conflict: %s", e.details.error_message)
            raise HttpError(409, "Organization name already in use. Try a different one.") from e
        logger.warning("Failed to create organization: %s", e.details.error_message)
        raise HttpError(400, "Failed to create organization.") from e

    # Sync to local database
    user, member, org = sync_session_to_local(
        stytch_member=response.member,
        stytch_organization=response.organization,
    )

    # Emit organization.created event
    publish_event(
        event_type="organization.created",
        aggregate=org,
        data={
            "name": org.name,
            "slug": org.slug,
            "stytch_org_id": org.stytch_org_id,
            "created_by_member_id": str(member.id),
        },
        actor=user,
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

    # Emit member.joined event (user joining existing org)
    publish_event(
        event_type="member.joined",
        aggregate=member,
        data={
            "email": user.email,
            "organization_name": org.name,
        },
        actor=user,
    )

    return SessionResponse(
        session_token=response.session_token,
        session_jwt=response.session_jwt,
        member_id=response.member.member_id,
        organization_id=response.organization.organization_id,
    )


# --- Mobile Provisioning ---


@router.post(
    "/mobile/provision",
    response={200: SessionResponse, 400: ErrorResponse, 401: ErrorResponse, 409: ErrorResponse},
    operation_id="provisionMobileUser",
    summary="Provision mobile user (API key auth)",
)
def provision_mobile_user_endpoint(
    request: HttpRequest,
    payload: MobileProvisionRequest,
) -> SessionResponse:
    """
    Provision a user for mobile app and return session tokens.

    Requires X-Mobile-API-Key header with valid API key.
    Creates user/member in Stytch and local DB, returns session credentials.

    Either provide organization_id to join an existing org,
    or organization_name + organization_slug to create a new one.
    """
    from django.conf import settings as django_settings

    # Validate API key
    api_key = request.headers.get("X-Mobile-API-Key")
    expected_key = django_settings.MOBILE_PROVISION_API_KEY

    if not expected_key:
        logger.error("MOBILE_PROVISION_API_KEY not configured")
        raise HttpError(401, "Mobile provisioning not configured")

    if not api_key or api_key != expected_key:
        raise HttpError(401, "Invalid or missing API key")

    try:
        user, member, org, session_token, session_jwt = provision_mobile_user(
            email=payload.email,
            name=payload.name,
            phone_number=payload.phone_number,
            organization_id=payload.organization_id,
            organization_name=payload.organization_name,
            organization_slug=payload.organization_slug,
        )
    except ValueError as e:
        raise HttpError(400, str(e)) from None
    except StytchError as e:
        error_msg = e.details.error_message.lower() if e.details.error_message else ""
        if "slug" in error_msg or "duplicate" in error_msg:
            logger.warning("Organization slug conflict: %s", e.details.error_message)
            raise HttpError(409, "Organization slug already in use. Try a different one.") from None
        logger.warning("Mobile provisioning failed: %s", e.details.error_message)
        raise HttpError(400, f"Provisioning failed: {e.details.error_message}") from None

    # Emit appropriate event
    if payload.organization_id:
        # Joined existing org
        publish_event(
            event_type="member.joined",
            aggregate=member,
            data={
                "email": user.email,
                "organization_name": org.name,
                "source": "mobile_provision",
            },
            actor=user,
        )
    else:
        # Created new org
        publish_event(
            event_type="organization.created",
            aggregate=org,
            data={
                "name": org.name,
                "slug": org.slug,
                "stytch_org_id": org.stytch_org_id,
                "created_by_member_id": str(member.id),
                "source": "mobile_provision",
            },
            actor=user,
        )

    return SessionResponse(
        session_token=session_token,
        session_jwt=session_jwt,
        member_id=member.stytch_member_id,
        organization_id=org.stytch_org_id,
    )


@router.post(
    "/logout",
    response={200: MessageResponse, 401: ErrorResponse},
    auth=bearer_auth,
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
    auth=bearer_auth,
    operation_id="getCurrentUser",
    summary="Get current user info",
)
def get_current_user(request: AuthenticatedHttpRequest) -> MeResponse:
    """
    Get current authenticated user, member, and organization info.

    Requires valid session JWT in Authorization header.
    """
    # These are set by the auth middleware
    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    user = request.auth_user
    member = request.auth_member
    org = request.auth_organization

    return MeResponse(
        user=UserInfo(
            id=user.id,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            phone_number=user.phone_number,
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
            logo_url=org.logo_url,
        ),
    )


# --- User Profile Settings ---


@router.patch(
    "/me/profile",
    response={200: UserInfo, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="updateProfile",
    summary="Update user profile",
)
def update_profile(request: AuthenticatedHttpRequest, payload: UpdateProfileRequest) -> UserInfo:
    """
    Update current user's profile (name only).

    Updates local database and syncs to Stytch.
    Phone number changes require OTP verification via /phone/verify-otp.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    user = request.auth_user
    member = request.auth_member
    org = request.auth_organization

    # Capture old name for event diff
    old_name = user.name

    # Update local database (name only - phone requires OTP verification)
    user.name = payload.name
    user.save(update_fields=["name", "updated_at"])

    # Sync name to Stytch
    try:
        client = get_stytch_client()
        client.organizations.members.update(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            name=payload.name,
        )
    except StytchError as e:
        logger.warning("Failed to sync name to Stytch: %s", e.details.error_message)
        # Don't fail the request - local update succeeded

    # Emit user.profile_updated event
    publish_event(
        event_type="user.profile_updated",
        aggregate=user,
        data={
            "old_name": old_name,
            "new_name": payload.name,
        },
        actor=user,
        organization_id=str(org.id),
    )

    return UserInfo(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        phone_number=user.phone_number,
    )


# --- Phone Verification ---


@router.post(
    "/phone/send-otp",
    response={200: PhoneOtpResponse, 400: ErrorResponse, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="sendPhoneOtp",
    summary="Send OTP to phone for verification",
)
def send_phone_otp(
    request: AuthenticatedHttpRequest, payload: SendPhoneOtpRequest
) -> PhoneOtpResponse:
    """
    Send a one-time password (OTP) to the specified phone number.

    The OTP is used to verify phone ownership before updating the user's profile.
    Uses Stytch's SMS OTP service.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    member = request.auth_member
    org = request.auth_organization

    # Extract session JWT from auth header
    auth_header = request.headers.get("Authorization", "")
    session_jwt = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None

    try:
        client = get_stytch_client()
        client.otps.sms.send(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            mfa_phone_number=payload.phone_number,
            session_jwt=session_jwt,
        )
        return PhoneOtpResponse(
            success=True,
            message=f"Verification code sent to {payload.phone_number}",
        )
    except StytchError as e:
        logger.warning("Failed to send phone OTP: %s", e.details.error_message)
        raise HttpError(
            400, e.details.error_message or "Failed to send verification code"
        ) from None


@router.post(
    "/phone/verify-otp",
    response={200: UserInfo, 400: ErrorResponse, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="verifyPhoneOtp",
    summary="Verify phone OTP and update profile",
)
def verify_phone_otp(request: AuthenticatedHttpRequest, payload: VerifyPhoneOtpRequest) -> UserInfo:
    """
    Verify the OTP sent to the phone number.

    On success, updates the user's phone number in both local database and Stytch.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    user = request.auth_user
    member = request.auth_member
    org = request.auth_organization

    # Extract session JWT from auth header (required by Stytch B2B OTP)
    auth_header = request.headers.get("Authorization", "")
    session_jwt = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None

    try:
        client = get_stytch_client()

        # Verify the OTP with Stytch
        # Note: Stytch B2B OTP requires a session field. For sessions created via
        # trusted auth (passkeys), this will fail with "immutable session" error.
        client.otps.sms.authenticate(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            code=payload.otp_code,
            session_jwt=session_jwt,
        )

        # OTP verified - now update the phone number
        old_phone = user.phone_number

        # Handle Stytch phone update (delete-then-update pattern)
        if old_phone:
            with contextlib.suppress(StytchError):
                client.organizations.members.delete_mfa_phone_number(
                    organization_id=org.stytch_org_id,
                    member_id=member.stytch_member_id,
                )

        # Set new phone number in Stytch
        client.organizations.members.update(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            mfa_phone_number=payload.phone_number,
        )

        # Update local database
        user.phone_number = payload.phone_number
        user.save(update_fields=["phone_number", "updated_at"])

        # Emit user.phone_changed event
        publish_event(
            event_type="user.phone_changed",
            aggregate=user,
            data={
                "old_phone": old_phone or "",
                "new_phone": payload.phone_number,
            },
            actor=user,
            organization_id=str(org.id),
        )

        return UserInfo(
            id=user.id,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            phone_number=user.phone_number,
        )

    except StytchError as e:
        error_msg = e.details.error_message or "Verification failed"
        if "invalid" in error_msg.lower() or "expired" in error_msg.lower():
            raise HttpError(400, "Invalid or expired verification code") from None
        if "immutable" in error_msg.lower():
            # Sessions created via passkey (trusted auth) are immutable and can't
            # have MFA factors added. User needs to re-authenticate via magic link.
            raise HttpError(
                400,
                "Phone verification is not available for passkey sessions. "
                "Please log out and sign in with email to update your phone number.",
            ) from None
        logger.warning("Phone OTP verification failed: %s", error_msg)
        raise HttpError(400, error_msg) from None


# --- Email Update ---


@router.post(
    "/email/start-update",
    response={200: EmailUpdateResponse, 400: ErrorResponse, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="startEmailUpdate",
    summary="Start email address update flow",
)
def start_email_update(
    request: AuthenticatedHttpRequest, payload: StartEmailUpdateRequest
) -> EmailUpdateResponse:
    """
    Initiate email address change.

    Sends a verification to the new email address. User must verify the new
    email to complete the change. The update is finalized via Stytch.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    user = request.auth_user
    member = request.auth_member
    org = request.auth_organization

    # Check if new email is the same as current
    if payload.new_email.lower() == user.email.lower():
        raise HttpError(400, "New email is the same as current email")

    try:
        client = get_stytch_client()
        # Update member email in Stytch - this triggers verification email
        client.organizations.members.update(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            email_address=payload.new_email,
        )
        return EmailUpdateResponse(
            success=True,
            message=f"Verification email sent to {payload.new_email}. Check your inbox to complete the change.",
        )
    except StytchError as e:
        error_msg = e.details.error_message or "Failed to initiate email update"
        logger.warning("Failed to start email update: %s", error_msg)
        raise HttpError(400, error_msg) from None


# --- Organization Settings (Admin Only) ---


@router.get(
    "/organization",
    response={200: OrganizationDetailResponse, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="getOrganization",
    summary="Get current organization details",
)
def get_organization(request: AuthenticatedHttpRequest) -> OrganizationDetailResponse:
    """
    Get current organization details including billing info.

    All authenticated members can view.
    """
    if not hasattr(request, "auth_organization") or request.auth_organization is None:
        raise HttpError(401, "Not authenticated")

    org = request.auth_organization

    return OrganizationDetailResponse(
        id=org.id,
        stytch_org_id=org.stytch_org_id,
        name=org.name,
        slug=org.slug,
        logo_url=org.logo_url,
        billing=BillingInfoResponse(
            use_billing_email=org.use_billing_email,
            billing_email=org.billing_email,
            billing_name=org.billing_name,
            address=BillingAddressSchema(
                line1=org.billing_address_line1,
                line2=org.billing_address_line2,
                city=org.billing_city,
                state=org.billing_state,
                postal_code=org.billing_postal_code,
                country=org.billing_country,
            ),
            vat_id=org.vat_id,
        ),
    )


@router.patch(
    "/organization",
    response={200: OrganizationDetailResponse, 401: ErrorResponse, 403: ErrorResponse},
    auth=bearer_auth,
    operation_id="updateOrganization",
    summary="Update organization settings",
)
@require_admin
def update_organization(
    request: AuthenticatedHttpRequest, payload: UpdateOrganizationRequest
) -> OrganizationDetailResponse:
    """
    Update organization settings (name).

    Admin only. Updates local database and syncs to Stytch.
    """
    assert request.auth_organization is not None  # Guaranteed by @require_admin
    org = request.auth_organization

    # Update local database
    update_fields = ["name", "updated_at"]
    org.name = payload.name
    if payload.slug is not None:
        org.slug = payload.slug
        update_fields.append("slug")
    org.save(update_fields=update_fields)

    # Sync to Stytch
    try:
        client = get_stytch_client()
        stytch_update_kwargs: dict[str, str] = {
            "organization_id": org.stytch_org_id,
            "organization_name": payload.name,
        }
        if payload.slug is not None:
            stytch_update_kwargs["organization_slug"] = payload.slug
        client.organizations.update(**stytch_update_kwargs)
    except StytchError as e:
        logger.warning("Failed to sync org to Stytch: %s", e.details.error_message)
        # Don't fail the request - local update succeeded

    # Emit organization.updated event
    publish_event(
        event_type="organization.updated",
        aggregate=org,
        data={
            "name": payload.name,
            "slug": payload.slug,
        },
        actor=request.auth_user,
    )

    return get_organization(request)


@router.patch(
    "/organization/billing",
    response={200: OrganizationDetailResponse, 401: ErrorResponse, 403: ErrorResponse},
    auth=bearer_auth,
    operation_id="updateBilling",
    summary="Update organization billing info",
)
@require_admin
def update_billing(
    request: AuthenticatedHttpRequest, payload: UpdateBillingRequest
) -> OrganizationDetailResponse:
    """
    Update organization billing info (address, VAT, etc.).

    Admin only. This is our system's data - synced out to Stripe.
    """
    assert request.auth_organization is not None  # Guaranteed by @require_admin
    org = request.auth_organization

    # Update billing fields
    org.use_billing_email = payload.use_billing_email
    if payload.billing_email is not None:
        org.billing_email = payload.billing_email
    org.billing_name = payload.billing_name
    org.vat_id = payload.vat_id

    if payload.address:
        org.billing_address_line1 = payload.address.line1
        org.billing_address_line2 = payload.address.line2
        org.billing_city = payload.address.city
        org.billing_state = payload.address.state
        org.billing_postal_code = payload.address.postal_code
        org.billing_country = payload.address.country

    org.save()

    # Sync billing info to Stripe
    if org.stripe_customer_id:
        try:
            sync_billing_to_stripe(org)
        except Exception as e:
            logger.warning("Failed to sync billing to Stripe: %s", e)
            # Don't fail the request - local update succeeded

    # Emit organization.billing_updated event
    publish_event(
        event_type="organization.billing_updated",
        aggregate=org,
        data={
            "billing_email": org.billing_email,
            "billing_name": org.billing_name,
            "vat_id": org.vat_id,
            "country": org.billing_country,
        },
        actor=request.auth_user,
    )

    return get_organization(request)


# --- Member Management (Admin Only) ---


@router.get(
    "/organization/members",
    response={200: MemberListResponse, 401: ErrorResponse, 403: ErrorResponse},
    auth=bearer_auth,
    operation_id="listMembers",
    summary="List organization members",
)
@require_admin
def list_members(
    request: AuthenticatedHttpRequest,
    offset: int = 0,
    limit: int | None = None,
) -> MemberListResponse:
    """
    List active members of the current organization with optional pagination.

    Admin only.

    Args:
        offset: Number of records to skip (default 0)
        limit: Maximum records to return (default None = all)
    """
    assert request.auth_organization is not None  # Guaranteed by @require_admin
    org = request.auth_organization
    all_members = list_organization_members(org)
    total = len(all_members)

    # Apply pagination
    if limit is not None:
        members = all_members[offset : offset + limit]
    else:
        members = all_members[offset:] if offset > 0 else all_members

    # Fetch member statuses from Stytch
    stytch = get_stytch_client()
    stytch_statuses: dict[str, str] = {}
    try:
        search_result = stytch.organizations.members.search(
            organization_ids=[org.stytch_org_id],
            query={"operator": "AND", "operands": []},
        )
        for stytch_member in search_result.members:
            stytch_statuses[stytch_member.member_id] = stytch_member.status
    except Exception:
        # If Stytch call fails, default to 'active'
        pass

    return MemberListResponse(
        members=[
            MemberListItem(
                id=m.id,
                stytch_member_id=m.stytch_member_id,
                email=m.user.email,
                name=m.user.name,
                role=m.role,
                is_admin=m.is_admin,
                status=stytch_statuses.get(m.stytch_member_id, "active"),
                created_at=m.created_at.isoformat(),
            )
            for m in members
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/organization/members",
    response={
        200: InviteMemberResponse,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="inviteMember",
    summary="Invite a new member",
)
@require_admin
def invite_member_endpoint(
    request: AuthenticatedHttpRequest, payload: InviteMemberRequest
) -> InviteMemberResponse:
    """
    Invite a new member to the organization.

    Admin only. Stytch sends the invite email with Magic Link.
    """
    assert request.auth_member is not None  # Guaranteed by @require_admin
    assert request.auth_organization is not None  # Guaranteed by @require_admin
    member = request.auth_member

    # Prevent inviting yourself
    if payload.email.lower() == member.user.email.lower():
        raise HttpError(400, "Cannot invite yourself - you're already a member")

    org = request.auth_organization

    try:
        new_member, invite_sent = invite_member(
            organization=org,
            email=payload.email,
            name=payload.name,
            role=payload.role,
        )
    except StytchError as e:
        logger.warning("Failed to invite member: %s", e.details.error_message)
        raise HttpError(400, f"Failed to invite member: {e.details.error_message}") from e

    if invite_sent is True:
        message = f"Invitation sent to {payload.email}"
    elif invite_sent == "pending":
        message = f"{payload.email} already has a pending invitation (role updated)"
    else:
        message = f"{payload.email} is already an active member (role updated)"

    # Emit member.invited event (only for new invites)
    if invite_sent is True:
        publish_event(
            event_type="member.invited",
            aggregate=new_member,
            data={
                "email": payload.email,
                "role": payload.role,
                "invited_by_member_id": str(member.id),
            },
            actor=member.user,
        )

    return InviteMemberResponse(
        message=message,
        stytch_member_id=new_member.stytch_member_id,
    )


@router.post(
    "/organization/members/bulk",
    response={
        200: BulkInviteResponse,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="bulkInviteMembers",
    summary="Bulk invite multiple members",
)
@require_admin
def bulk_invite_members_endpoint(
    request: AuthenticatedHttpRequest, payload: BulkInviteRequest
) -> BulkInviteResponse:
    """
    Invite multiple members to the organization at once.

    Admin only. Processes each invite individually, allowing partial success.
    Phone numbers are stored unverified (will require OTP verification later).

    Returns detailed results for each member attempted.
    """
    assert request.auth_member is not None  # Guaranteed by @require_admin
    assert request.auth_organization is not None  # Guaranteed by @require_admin
    member = request.auth_member
    org = request.auth_organization

    current_user_email = member.user.email.lower()

    # Filter out self-invites, normalize emails
    members_data = []
    skipped_results = []
    for item in payload.members:
        # Normalize email: strip whitespace and lowercase for comparison
        normalized_email = item.email.strip().lower()

        if normalized_email == current_user_email:
            skipped_results.append(
                {
                    "email": item.email.strip(),
                    "success": False,
                    "error": "Cannot invite yourself",
                    "stytch_member_id": None,
                }
            )
            continue

        members_data.append(
            {
                "email": item.email.strip(),  # Use stripped email
                "name": item.name.strip() if item.name else "",
                "phone": item.phone.strip() if item.phone else "",
                "role": item.role,
            }
        )

    if not members_data:
        # All members were skipped (self-invites or existing members)
        return BulkInviteResponse(
            results=[
                BulkInviteResultItem(
                    email=r["email"],
                    success=r["success"],
                    error=r["error"],
                    stytch_member_id=r["stytch_member_id"],
                )
                for r in skipped_results
            ],
            total=len(skipped_results),
            succeeded=0,
            failed=len(skipped_results),
        )

    result = bulk_invite_members(organization=org, members_data=members_data)

    # Emit member.bulk_invited event for successful invites
    successful_emails = [r["email"] for r in result["results"] if r["success"]]
    if successful_emails:
        publish_event(
            event_type="member.bulk_invited",
            aggregate=org,
            data={
                "emails": successful_emails,
                "count": len(successful_emails),
                "invited_by_member_id": str(member.id),
            },
            actor=member.user,
        )

    # Combine skipped results with actual invite results
    all_results = skipped_results + result["results"]

    return BulkInviteResponse(
        results=[
            BulkInviteResultItem(
                email=r["email"],
                success=r["success"],
                error=r["error"],
                stytch_member_id=r["stytch_member_id"],
            )
            for r in all_results
        ],
        total=len(all_results),
        succeeded=result["succeeded"],
        failed=result["failed"] + len(skipped_results),
    )


@router.patch(
    "/organization/members/{member_id}",
    response={
        200: MessageResponse,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="updateMemberRole",
    summary="Update member role",
)
@require_admin
def update_member_role_endpoint(
    request: AuthenticatedHttpRequest, member_id: int, payload: UpdateMemberRoleRequest
) -> MessageResponse:
    """
    Update a member's role (admin or member).

    Admin only. Cannot change your own role.
    """
    assert request.auth_member is not None  # Guaranteed by @require_admin
    assert request.auth_organization is not None  # Guaranteed by @require_admin
    current_member = request.auth_member
    org = request.auth_organization

    # Find the target member
    try:
        target_member = Member.objects.select_related("organization").get(
            id=member_id, organization=org
        )
    except Member.DoesNotExist:
        raise HttpError(404, "Member not found") from None

    # Prevent changing own role
    if target_member.id == current_member.id:
        raise HttpError(400, "Cannot change your own role")

    # Capture old role before update
    old_role = target_member.role

    try:
        update_member_role(target_member, payload.role)
    except StytchError as e:
        logger.warning("Failed to update member role: %s", e.details.error_message)
        raise HttpError(400, f"Failed to update role: {e.details.error_message}") from e

    # Emit member.role_changed event
    publish_event(
        event_type="member.role_changed",
        aggregate=target_member,
        data={
            "old_role": old_role,
            "new_role": payload.role,
            "changed_by_member_id": str(current_member.id),
        },
        actor=current_member.user,
    )

    return MessageResponse(message=f"Role updated to {payload.role}")


@router.delete(
    "/organization/members/{member_id}",
    response={
        200: MessageResponse,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="deleteMember",
    summary="Remove member from organization",
)
@require_admin
def delete_member_endpoint(request: AuthenticatedHttpRequest, member_id: int) -> MessageResponse:
    """
    Remove a member from the organization.

    Admin only. Cannot remove yourself. Soft deletes locally
    and removes from Stytch.
    """
    assert request.auth_member is not None  # Guaranteed by @require_admin
    assert request.auth_organization is not None  # Guaranteed by @require_admin
    current_member = request.auth_member
    org = request.auth_organization

    # Find the target member
    try:
        target_member = Member.objects.select_related("organization", "user").get(
            id=member_id, organization=org
        )
    except Member.DoesNotExist:
        raise HttpError(404, "Member not found") from None

    # Prevent removing yourself
    if target_member.id == current_member.id:
        raise HttpError(400, "Cannot remove yourself")

    email = target_member.user.email

    try:
        soft_delete_member(target_member)
    except StytchError as e:
        logger.warning("Failed to delete member: %s", e.details.error_message)
        raise HttpError(400, f"Failed to remove member: {e.details.error_message}") from e

    # Emit member.removed event
    publish_event(
        event_type="member.removed",
        aggregate=target_member,
        data={
            "email": email,
            "removed_by_member_id": str(current_member.id),
        },
        actor=current_member.user,
    )

    return MessageResponse(message=f"Member {email} removed from organization")


# --- Google Directory Search ---


@router.get(
    "/directory/search",
    response={200: list[DirectoryUserSchema], 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="searchDirectory",
    summary="Search Google Workspace directory for users",
)
def search_directory(request: AuthenticatedHttpRequest, q: str = "") -> list[DirectoryUserSchema]:
    """
    Search Google Workspace directory for coworkers.

    Returns matching users from the authenticated user's Google Workspace domain.
    Only works if the user has signed in with Google OAuth and granted
    the Directory API scope. Returns empty list if not available.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    if not q or len(q) < 2:
        return []

    user = request.auth_user
    member = request.auth_member

    # Import here to avoid circular imports
    from apps.accounts.google_directory import search_directory_users

    directory_users = search_directory_users(user, member, q, limit=10)

    return [
        DirectoryUserSchema(
            email=u.email,
            name=u.name,
            avatar_url=u.avatar_url,
        )
        for u in directory_users
    ]


@router.get(
    "/directory/avatar",
    response={200: bytes, 400: ErrorResponse, 401: ErrorResponse, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="getDirectoryAvatar",
    summary="Proxy Google Workspace avatar image",
)
def get_directory_avatar(request: AuthenticatedHttpRequest, url: str = ""):
    """
    Proxy a Google Workspace avatar image.

    Google Directory API avatar URLs require OAuth authentication.
    This endpoint fetches the image server-side and returns it.

    Only allows fetching from Google user content domains (SSRF protection).
    """
    import httpx
    from django.http import HttpResponse as DjangoHttpResponse

    from apps.core.url_validation import SSRFError, validate_avatar_url

    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    # Validate URL against SSRF attacks
    try:
        validate_avatar_url(url)
    except SSRFError as e:
        logger.warning("Avatar URL validation failed: %s (url=%s)", e, url)
        raise HttpError(400, "Invalid avatar URL") from None

    # Import here to avoid circular imports
    from apps.accounts.google_directory import get_google_access_token
    from apps.accounts.models import Member

    user = request.auth_user

    # Get member to find Stytch IDs
    member = (
        Member.objects.filter(user=user, deleted_at__isnull=True)
        .select_related("organization")
        .first()
    )

    if not member:
        raise HttpError(404, "No member found")

    access_token = get_google_access_token(
        organization_id=member.organization.stytch_org_id,
        member_id=member.stytch_member_id,
    )

    if not access_token:
        raise HttpError(404, "No Google OAuth token")

    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
            follow_redirects=True,
        )
        response.raise_for_status()

        return DjangoHttpResponse(
            response.content,
            content_type=response.headers.get("content-type", "image/jpeg"),
        )
    except httpx.HTTPError:
        raise HttpError(404, "Failed to fetch avatar") from None
