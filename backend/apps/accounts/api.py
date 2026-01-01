"""
Auth API endpoints.

Handles Stytch B2B authentication flows:
- Magic link send/authenticate
- Discovery org creation/exchange
- Session management
- User profile and organization settings
"""

import logging

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from stytch.core.response_base import StytchError

from apps.accounts.schemas import (
    BillingAddressSchema,
    BillingInfoResponse,
    DiscoveredOrganization,
    DiscoveryCreateOrgRequest,
    DiscoveryExchangeRequest,
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
    OrganizationDetailResponse,
    OrganizationInfo,
    PhoneOtpResponse,
    SendPhoneOtpRequest,
    SessionResponse,
    UpdateBillingRequest,
    UpdateMemberRoleRequest,
    UpdateOrganizationRequest,
    UpdateProfileRequest,
    UserInfo,
    VerifyPhoneOtpRequest,
)
from apps.accounts.services import (
    invite_member,
    list_organization_members,
    soft_delete_member,
    sync_session_to_local,
    update_member_role,
)
from apps.accounts.stytch_client import get_stytch_client
from apps.core.schemas import ErrorResponse
from apps.core.security import BearerAuth, require_admin

logger = logging.getLogger(__name__)

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
def update_profile(request: HttpRequest, payload: UpdateProfileRequest) -> UserInfo:
    """
    Update current user's profile (name only).

    Updates local database and syncs to Stytch.
    Phone number changes require OTP verification via /phone/verify-otp.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:  # type: ignore[attr-defined]
        raise HttpError(401, "Not authenticated")

    user = request.auth_user  # type: ignore[attr-defined]
    member = request.auth_member  # type: ignore[attr-defined]
    org = request.auth_organization  # type: ignore[attr-defined]

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
def send_phone_otp(request: HttpRequest, payload: SendPhoneOtpRequest) -> PhoneOtpResponse:
    """
    Send a one-time password (OTP) to the specified phone number.

    The OTP is used to verify phone ownership before updating the user's profile.
    Uses Stytch's SMS OTP service.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:  # type: ignore[attr-defined]
        raise HttpError(401, "Not authenticated")

    member = request.auth_member  # type: ignore[attr-defined]
    org = request.auth_organization  # type: ignore[attr-defined]

    try:
        client = get_stytch_client()
        client.otps.sms.send(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            mfa_phone_number=payload.phone_number,
        )
        return PhoneOtpResponse(
            success=True,
            message=f"Verification code sent to {payload.phone_number}",
        )
    except StytchError as e:
        logger.warning("Failed to send phone OTP: %s", e.details.error_message)
        raise HttpError(400, e.details.error_message or "Failed to send verification code")


@router.post(
    "/phone/verify-otp",
    response={200: UserInfo, 400: ErrorResponse, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="verifyPhoneOtp",
    summary="Verify phone OTP and update profile",
)
def verify_phone_otp(request: HttpRequest, payload: VerifyPhoneOtpRequest) -> UserInfo:
    """
    Verify the OTP sent to the phone number.

    On success, updates the user's phone number in both local database and Stytch.
    """
    if not hasattr(request, "auth_user") or request.auth_user is None:  # type: ignore[attr-defined]
        raise HttpError(401, "Not authenticated")

    user = request.auth_user  # type: ignore[attr-defined]
    member = request.auth_member  # type: ignore[attr-defined]
    org = request.auth_organization  # type: ignore[attr-defined]

    try:
        client = get_stytch_client()

        # Verify the OTP with Stytch
        client.otps.sms.authenticate(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            code=payload.otp_code,
        )

        # OTP verified - now update the phone number
        old_phone = user.phone_number

        # Handle Stytch phone update (delete-then-update pattern)
        if old_phone:
            try:
                client.organizations.members.delete_phone_number(
                    organization_id=org.stytch_org_id,
                    member_id=member.stytch_member_id,
                )
            except StytchError:
                pass  # No phone to delete

        # Set new phone number in Stytch
        client.organizations.members.update(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            mfa_phone_number=payload.phone_number,
        )

        # Update local database
        user.phone_number = payload.phone_number
        user.save(update_fields=["phone_number", "updated_at"])

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
            raise HttpError(400, "Invalid or expired verification code")
        logger.warning("Phone OTP verification failed: %s", error_msg)
        raise HttpError(400, error_msg)


# --- Organization Settings (Admin Only) ---


@router.get(
    "/organization",
    response={200: OrganizationDetailResponse, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="getOrganization",
    summary="Get current organization details",
)
def get_organization(request: HttpRequest) -> OrganizationDetailResponse:
    """
    Get current organization details including billing info.

    All authenticated members can view.
    """
    if not hasattr(request, "auth_organization") or request.auth_organization is None:  # type: ignore[attr-defined]
        raise HttpError(401, "Not authenticated")

    org = request.auth_organization  # type: ignore[attr-defined]

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
    request: HttpRequest, payload: UpdateOrganizationRequest
) -> OrganizationDetailResponse:
    """
    Update organization settings (name).

    Admin only. Updates local database and syncs to Stytch.
    """
    org = request.auth_organization  # type: ignore[attr-defined]

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
    request: HttpRequest, payload: UpdateBillingRequest
) -> OrganizationDetailResponse:
    """
    Update organization billing info (address, VAT, etc.).

    Admin only. This is our system's data - synced out to Stripe.
    """
    org = request.auth_organization  # type: ignore[attr-defined]

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
            from apps.billing.services import sync_billing_to_stripe

            sync_billing_to_stripe(org)
        except Exception as e:
            logger.warning("Failed to sync billing to Stripe: %s", e)
            # Don't fail the request - local update succeeded

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
def list_members(request: HttpRequest) -> MemberListResponse:
    """
    List all active members of the current organization.

    Admin only.
    """
    org = request.auth_organization  # type: ignore[attr-defined]
    members = list_organization_members(org)

    # Fetch member statuses from Stytch
    from apps.accounts.stytch_client import get_stytch_client

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
        ]
    )


@router.post(
    "/organization/members",
    response={200: InviteMemberResponse, 400: ErrorResponse, 401: ErrorResponse, 403: ErrorResponse},
    auth=bearer_auth,
    operation_id="inviteMember",
    summary="Invite a new member",
)
@require_admin
def invite_member_endpoint(
    request: HttpRequest, payload: InviteMemberRequest
) -> InviteMemberResponse:
    """
    Invite a new member to the organization.

    Admin only. Stytch sends the invite email with Magic Link.
    """
    member = request.auth_member  # type: ignore[attr-defined]

    # Prevent inviting yourself
    if payload.email.lower() == member.user.email.lower():
        raise HttpError(400, "Cannot invite yourself - you're already a member")

    org = request.auth_organization  # type: ignore[attr-defined]

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

    return InviteMemberResponse(
        message=message,
        stytch_member_id=new_member.stytch_member_id,
    )


@router.patch(
    "/organization/members/{member_id}",
    response={200: MessageResponse, 400: ErrorResponse, 401: ErrorResponse, 403: ErrorResponse, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="updateMemberRole",
    summary="Update member role",
)
@require_admin
def update_member_role_endpoint(
    request: HttpRequest, member_id: int, payload: UpdateMemberRoleRequest
) -> MessageResponse:
    """
    Update a member's role (admin or member).

    Admin only. Cannot change your own role.
    """
    from apps.accounts.models import Member

    current_member = request.auth_member  # type: ignore[attr-defined]
    org = request.auth_organization  # type: ignore[attr-defined]

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

    try:
        update_member_role(target_member, payload.role)
    except StytchError as e:
        logger.warning("Failed to update member role: %s", e.details.error_message)
        raise HttpError(400, f"Failed to update role: {e.details.error_message}") from e

    return MessageResponse(message=f"Role updated to {payload.role}")


@router.delete(
    "/organization/members/{member_id}",
    response={200: MessageResponse, 400: ErrorResponse, 401: ErrorResponse, 403: ErrorResponse, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="deleteMember",
    summary="Remove member from organization",
)
@require_admin
def delete_member_endpoint(request: HttpRequest, member_id: int) -> MessageResponse:
    """
    Remove a member from the organization.

    Admin only. Cannot remove yourself. Soft deletes locally
    and removes from Stytch.
    """
    from apps.accounts.models import Member

    current_member = request.auth_member  # type: ignore[attr-defined]
    org = request.auth_organization  # type: ignore[attr-defined]

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

    return MessageResponse(message=f"Member {email} removed from organization")


