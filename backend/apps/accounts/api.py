"""
Auth API endpoints.

Handles Stytch B2B authentication flows:
- Magic link send/authenticate
- Discovery org creation/exchange
- Session management
- User profile and organization settings
"""

import contextlib
import secrets

from django.conf import settings as django_settings
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
    provision_mobile_user,
    soft_delete_member,
    sync_session_to_local,
    update_member_role,
)
from apps.accounts.stytch_client import get_stytch_client
from apps.billing.services import sync_billing_to_stripe
from apps.core.logging import get_logger
from apps.core.schemas import ErrorResponse
from apps.core.security import BearerAuth, get_auth_context, require_admin
from apps.core.throttling import RateLimitExceeded, check_rate_limit
from apps.core.types import AuthenticatedHttpRequest
from apps.core.utils import get_client_ip
from apps.events.services import publish_event

logger = get_logger(__name__)

router = Router(tags=["auth"])
bearer_auth = BearerAuth()


def _extract_bearer_token(request: HttpRequest) -> str | None:
    """Extract JWT from Authorization: Bearer header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "")
    return None


def _get_stytch_error_message(error: StytchError) -> str:
    """Extract error message from StytchError, lowercase for comparison."""
    if error.details and error.details.error_message:
        return error.details.error_message.lower()
    return ""


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
    try:
        client_ip = get_client_ip(request, default="unknown")
        check_rate_limit(
            f"magic_link_send:email:{payload.email.lower()}",
            max_requests=django_settings.AUTH_RATE_LIMIT_MAGIC_LINK_SEND_PER_EMAIL,
            window_seconds=django_settings.AUTH_RATE_LIMIT_MAGIC_LINK_SEND_WINDOW,
        )
        check_rate_limit(
            f"magic_link_send:ip:{client_ip}",
            max_requests=django_settings.AUTH_RATE_LIMIT_MAGIC_LINK_SEND_PER_IP,
            window_seconds=django_settings.AUTH_RATE_LIMIT_MAGIC_LINK_SEND_WINDOW,
        )
    except RateLimitExceeded as e:
        raise HttpError(429, str(e)) from None

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
    try:
        client_ip = get_client_ip(request, default="unknown")
        check_rate_limit(
            f"magic_link_auth:ip:{client_ip}",
            max_requests=django_settings.AUTH_RATE_LIMIT_TOKEN_AUTH_PER_IP,
            window_seconds=django_settings.AUTH_RATE_LIMIT_TOKEN_AUTH_WINDOW,
        )
    except RateLimitExceeded as e:
        raise HttpError(429, str(e)) from None

    client = get_stytch_client()

    try:
        response = client.magic_links.discovery.authenticate(
            discovery_magic_links_token=payload.token,
        )
    except StytchError as e:
        logger.warning("Magic link authentication failed: %s", e.details.error_message)
        raise HttpError(400, "Invalid or expired token.") from e

    # Build list of discovered organizations
    # Stytch SDK types organization as Optional but it's always present in discovered_organizations
    discovered_orgs = [
        DiscoveredOrganization(
            organization_id=org.organization.organization_id,  # type: ignore[union-attr]
            organization_name=org.organization.organization_name,  # type: ignore[union-attr]
            organization_slug=org.organization.organization_slug,  # type: ignore[union-attr]
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
    try:
        client_ip = get_client_ip(request, default="unknown")
        check_rate_limit(
            f"discovery_create_org:ip:{client_ip}",
            max_requests=django_settings.AUTH_RATE_LIMIT_ORG_CREATE_PER_IP,
            window_seconds=django_settings.AUTH_RATE_LIMIT_ORG_CREATE_WINDOW,
        )
    except RateLimitExceeded as e:
        raise HttpError(429, str(e)) from None

    client = get_stytch_client()

    try:
        response = client.discovery.organizations.create(
            intermediate_session_token=payload.intermediate_session_token,
            organization_name=payload.organization_name,
            organization_slug=payload.organization_slug,
        )
    except StytchError as e:
        error_msg = _get_stytch_error_message(e)
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

    # Stytch SDK types organization as Optional but it's always present after successful creation
    return SessionResponse(
        session_token=response.session_token,
        session_jwt=response.session_jwt,
        member_id=response.member.member_id,
        organization_id=response.organization.organization_id,  # type: ignore[union-attr]
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
    try:
        client_ip = get_client_ip(request, default="unknown")
        check_rate_limit(
            f"discovery_exchange:ip:{client_ip}",
            max_requests=django_settings.AUTH_RATE_LIMIT_TOKEN_AUTH_PER_IP,
            window_seconds=django_settings.AUTH_RATE_LIMIT_TOKEN_AUTH_WINDOW,
        )
    except RateLimitExceeded as e:
        raise HttpError(429, str(e)) from None

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
    try:
        client_ip = get_client_ip(request, default="unknown")
        check_rate_limit(
            f"mobile_provision:ip:{client_ip}",
            max_requests=django_settings.AUTH_RATE_LIMIT_MOBILE_PROVISION_PER_IP,
            window_seconds=django_settings.AUTH_RATE_LIMIT_MOBILE_PROVISION_WINDOW,
        )
    except RateLimitExceeded as e:
        raise HttpError(429, str(e)) from None

    # Validate API key
    api_key = request.headers.get("X-Mobile-API-Key")
    expected_key = django_settings.MOBILE_PROVISION_API_KEY

    if not expected_key:
        logger.error("MOBILE_PROVISION_API_KEY not configured")
        raise HttpError(401, "Mobile provisioning not configured")

    if not api_key or not secrets.compare_digest(api_key, expected_key):
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
        error_msg = _get_stytch_error_message(e)
        if "slug" in error_msg or "duplicate" in error_msg:
            logger.warning("Organization slug conflict: %s", e.details.error_message)
            raise HttpError(409, "Organization slug already in use. Try a different one.") from None
        logger.warning("Mobile provisioning failed: %s", e.details.error_message)
        raise HttpError(400, "Provisioning failed. Please try again.") from None

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
    user, member, org = get_auth_context(request)

    return MeResponse(
        user=UserInfo.from_model(user),
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
    user, member, org = get_auth_context(request)

    # Capture old name for event diff
    old_name = user.name

    # Update local database (name only - phone requires OTP verification)
    user.name = payload.name
    user.save(update_fields=["name", "updated_at"])

    # Sync name to Stytch
    sync_warning = None
    try:
        client = get_stytch_client()
        client.organizations.members.update(
            organization_id=org.stytch_org_id,
            member_id=member.stytch_member_id,
            name=payload.name,
        )
    except StytchError as e:
        logger.warning(
            "Failed to sync name to Stytch: %s (org=%s, member=%s)",
            e.details.error_message,
            org.stytch_org_id,
            member.stytch_member_id,
            exc_info=True,
        )
        sync_warning = (
            "Changes saved locally but failed to sync to Stytch. "
            "Please retry or contact support if the issue persists."
        )

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

    response = UserInfo.from_model(user)
    if sync_warning:
        response.sync_warning = sync_warning
    return response


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
    _, member, org = get_auth_context(request)

    session_jwt = _extract_bearer_token(request)

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
        logger.warning("Failed to send phone OTP: %r", e, exc_info=True)
        raise HttpError(400, "Failed to send verification code.") from None


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
    user, member, org = get_auth_context(request)

    session_jwt = _extract_bearer_token(request)

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

        # Sync phone to Stytch (non-fatal if it fails after OTP verification)
        sync_warning = None
        try:
            if old_phone:
                with contextlib.suppress(StytchError):
                    client.organizations.members.delete_mfa_phone_number(
                        organization_id=org.stytch_org_id,
                        member_id=member.stytch_member_id,
                    )

            client.organizations.members.update(
                organization_id=org.stytch_org_id,
                member_id=member.stytch_member_id,
                mfa_phone_number=payload.phone_number,
            )
        except StytchError as e:
            logger.warning(
                "Failed to sync phone to Stytch: %r (org=%s, member=%s)",
                e,
                org.stytch_org_id,
                member.stytch_member_id,
                exc_info=True,
            )
            sync_warning = (
                "Phone verified and saved locally but failed to sync to Stytch. "
                "Please retry or contact support if the issue persists."
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

        response = UserInfo.from_model(user)
        if sync_warning:
            response.sync_warning = sync_warning
        return response

    except StytchError as e:
        error_msg = _get_stytch_error_message(e)
        if "invalid" in error_msg or "expired" in error_msg:
            logger.warning(
                "Phone OTP verification failed (invalid/expired): %s", e.details.error_message
            )
            raise HttpError(400, "Invalid or expired verification code.") from None
        if "immutable" in error_msg:
            # Sessions created via passkey (trusted auth) are immutable and can't
            # have MFA factors added. User needs to re-authenticate via magic link.
            logger.warning(
                "Phone OTP verification failed (immutable session): %s", e.details.error_message
            )
            raise HttpError(
                400,
                "Phone verification is not available for passkey sessions. "
                "Please log out and sign in with email to update your phone number.",
            ) from None
        logger.warning("Phone OTP verification failed: %s", e.details.error_message)
        raise HttpError(400, "Verification failed. Please try again.") from None


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
    user, member, org = get_auth_context(request)

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
        logger.warning("Failed to start email update: %s", e.details.error_message)
        raise HttpError(400, "Failed to initiate email update. Please try again.") from None


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
    _, _, org = get_auth_context(request)

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
    _, _, org = get_auth_context(request)

    # Update local database
    update_fields = ["name", "updated_at"]
    org.name = payload.name
    if payload.slug is not None:
        org.slug = payload.slug
        update_fields.append("slug")
    org.save(update_fields=update_fields)

    # Sync to Stytch
    sync_warning = None
    try:
        client = get_stytch_client()
        stytch_update_kwargs: dict[str, str] = {
            "organization_id": org.stytch_org_id,
            "organization_name": payload.name,
        }
        if payload.slug is not None:
            stytch_update_kwargs["organization_slug"] = payload.slug
        # Stytch SDK has complex overloaded types; we only use simple string params
        client.organizations.update(**stytch_update_kwargs)  # type: ignore[arg-type]
    except StytchError as e:
        logger.warning(
            "Failed to sync org to Stytch: %s (org=%s)",
            e.details.error_message,
            org.stytch_org_id,
            exc_info=True,
        )
        sync_warning = (
            "Changes saved locally but failed to sync to Stytch. "
            "Please retry or contact support if the issue persists."
        )

    # Emit organization.updated event
    publish_event(
        event_type="organization.updated",
        aggregate=org,
        data={
            "name": payload.name,
            "slug": payload.slug,
        },
        actor=request.auth.user,
    )

    response = get_organization(request)
    if sync_warning:
        response.sync_warning = sync_warning
    return response


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
    _, _, org = get_auth_context(request)

    # Update billing fields
    org.use_billing_email = payload.use_billing_email
    if payload.billing_email is not None:
        org.billing_email = payload.billing_email
    elif not payload.use_billing_email:
        # Clear stale billing email when disabling the feature
        org.billing_email = ""
    org.billing_name = payload.billing_name
    org.vat_id = payload.vat_id

    update_fields = [
        "use_billing_email",
        "billing_email",
        "billing_name",
        "vat_id",
        "updated_at",
    ]

    if payload.address:
        org.billing_address_line1 = payload.address.line1
        org.billing_address_line2 = payload.address.line2
        org.billing_city = payload.address.city
        org.billing_state = payload.address.state
        org.billing_postal_code = payload.address.postal_code
        org.billing_country = payload.address.country
        update_fields.extend(
            [
                "billing_address_line1",
                "billing_address_line2",
                "billing_city",
                "billing_state",
                "billing_postal_code",
                "billing_country",
            ]
        )

    org.save(update_fields=update_fields)

    # Sync billing info to Stripe
    sync_warning = None
    if org.stripe_customer_id:
        try:
            sync_billing_to_stripe(org)
        except Exception as e:
            logger.warning(
                "Failed to sync billing to Stripe: %s (org=%s, stripe_customer=%s)",
                e,
                org.stytch_org_id,
                org.stripe_customer_id,
                exc_info=True,
            )
            sync_warning = (
                "Changes saved locally but failed to sync to Stripe. "
                "Please retry or contact support if the issue persists."
            )

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
        actor=request.auth.user,
    )

    response = get_organization(request)
    if sync_warning:
        response.sync_warning = sync_warning
    return response


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
    cursor: str | None = None,
    limit: int = 20,
) -> MemberListResponse:
    """
    List active members of the current organization with cursor-based pagination.

    Admin only. Uses Stytch's server-side pagination to avoid fetching all members.

    Args:
        cursor: Pagination cursor from a previous response (null for first page)
        limit: Maximum records to return per page (default 20, max 100)
    """
    _, _, org = get_auth_context(request)

    # Clamp limit to a reasonable range
    limit = max(1, min(limit, 100))

    # Fetch paginated members from Stytch with cursor-based pagination
    stytch = get_stytch_client()
    stytch_members_data: list[dict[str, str]] = []
    next_cursor: str | None = None
    total = 0

    try:
        search_kwargs: dict = {
            "organization_ids": [org.stytch_org_id],
            "query": {"operator": "AND", "operands": []},
            "limit": limit,
        }
        if cursor:
            search_kwargs["cursor"] = cursor

        search_result = stytch.organizations.members.search(**search_kwargs)

        for stytch_member in search_result.members:
            stytch_members_data.append(
                {
                    "member_id": stytch_member.member_id,
                    "status": stytch_member.status,
                }
            )

        # Extract pagination metadata from Stytch response
        total = getattr(search_result, "total_count", 0) or 0
        next_cursor = getattr(search_result, "next_cursor", None) or None
    except StytchError:
        logger.warning("stytch_member_search_failed", org_id=org.id, exc_info=True)

    # Build a lookup of Stytch member statuses
    stytch_statuses: dict[str, str] = {m["member_id"]: m["status"] for m in stytch_members_data}
    stytch_member_ids = [m["member_id"] for m in stytch_members_data]

    # Fetch local member records for the Stytch members in this page
    local_members = (
        Member.objects.filter(
            organization=org,
            stytch_member_id__in=stytch_member_ids,
            deleted_at__isnull=True,
        )
        .select_related("user")
        .order_by("created_at")
    )

    # Build a lookup by stytch_member_id to preserve Stytch's page order
    local_by_stytch_id = {m.stytch_member_id: m for m in local_members}

    # If no Stytch results (e.g., Stytch call failed), fall back to local DB.
    # Apply the same limit to cap response size, but set has_more=False since
    # we cannot provide a cursor for subsequent pages in degraded mode.
    if not stytch_members_data:
        local_fallback = (
            Member.objects.filter(organization=org, deleted_at__isnull=True)
            .select_related("user")
            .order_by("created_at")
        )
        total = local_fallback.count()
        return MemberListResponse(
            members=[
                MemberListItem(
                    id=m.id,
                    stytch_member_id=m.stytch_member_id,
                    email=m.user.email,
                    name=m.user.name,
                    role=m.role,
                    is_admin=m.is_admin,
                    status="active",
                    created_at=m.created_at.isoformat(),
                )
                for m in local_fallback[:limit]
            ],
            total=total,
            next_cursor=None,
            has_more=False,
        )

    return MemberListResponse(
        members=[
            MemberListItem(
                id=local_by_stytch_id[sid].id,
                stytch_member_id=sid,
                email=local_by_stytch_id[sid].user.email,
                name=local_by_stytch_id[sid].user.name,
                role=local_by_stytch_id[sid].role,
                is_admin=local_by_stytch_id[sid].is_admin,
                status=stytch_statuses.get(sid, "active"),
                created_at=local_by_stytch_id[sid].created_at.isoformat(),
            )
            for sid in stytch_member_ids
            if sid in local_by_stytch_id
        ],
        total=total,
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
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
    _, member, org = get_auth_context(request)

    # Prevent inviting yourself
    if payload.email.lower() == member.user.email.lower():
        raise HttpError(400, "Cannot invite yourself - you're already a member")

    try:
        new_member, invite_sent = invite_member(
            organization=org,
            email=payload.email,
            name=payload.name,
            role=payload.role,
        )
    except StytchError as e:
        logger.warning("Failed to invite member: %s", e.details.error_message)
        raise HttpError(400, "Failed to invite member. Please try again.") from e

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
    _, member, org = get_auth_context(request)

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
                    email=str(r["email"]),
                    success=bool(r["success"]),
                    error=str(r["error"]) if r["error"] else None,
                    stytch_member_id=str(r["stytch_member_id"]) if r["stytch_member_id"] else None,
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
                email=str(r["email"]),
                success=bool(r["success"]),
                error=str(r["error"]) if r["error"] else None,
                stytch_member_id=str(r["stytch_member_id"]) if r["stytch_member_id"] else None,
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
    request: AuthenticatedHttpRequest, member_id: str, payload: UpdateMemberRoleRequest
) -> MessageResponse:
    """
    Update a member's role (admin or member).

    Admin only. Cannot change your own role.
    Member ID is the Stytch member ID (e.g., "member-xxx").
    """
    _, current_member, org = get_auth_context(request)

    # Find the target member by stytch_member_id
    try:
        target_member = Member.objects.select_related("organization").get(
            stytch_member_id=member_id, organization=org
        )
    except Member.DoesNotExist:
        raise HttpError(404, "Member not found") from None

    # Prevent changing own role
    if target_member.stytch_member_id == current_member.stytch_member_id:
        raise HttpError(400, "Cannot change your own role")

    # Capture old role before update
    old_role = target_member.role

    try:
        update_member_role(target_member, payload.role)
    except StytchError as e:
        logger.warning("Failed to update member role: %s", e.details.error_message)
        raise HttpError(400, "Failed to update role. Please try again.") from e

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
def delete_member_endpoint(request: AuthenticatedHttpRequest, member_id: str) -> MessageResponse:
    """
    Remove a member from the organization.

    Admin only. Cannot remove yourself. Soft deletes locally
    and removes from Stytch.
    Member ID is the Stytch member ID (e.g., "member-xxx").
    """
    _, current_member, org = get_auth_context(request)

    # Find the target member by stytch_member_id
    try:
        target_member = Member.objects.select_related("organization", "user").get(
            stytch_member_id=member_id, organization=org
        )
    except Member.DoesNotExist:
        raise HttpError(404, "Member not found") from None

    # Prevent removing yourself
    if target_member.stytch_member_id == current_member.stytch_member_id:
        raise HttpError(400, "Cannot remove yourself")

    email = target_member.user.email

    try:
        soft_delete_member(target_member)
    except StytchError as e:
        logger.warning("Failed to remove member: %s", e.details.error_message)
        raise HttpError(400, "Failed to remove member. Please try again.") from e

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
    user, member, _ = get_auth_context(request)

    if not q or len(q) < 2:
        return []

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

    user, _, _ = get_auth_context(request)

    # Validate URL against SSRF attacks
    try:
        validate_avatar_url(url)
    except SSRFError as e:
        logger.warning("Avatar URL validation failed: %s (url=%s)", e, url)
        raise HttpError(400, "Invalid avatar URL") from None

    # Import here to avoid circular imports
    from apps.accounts.google_directory import get_google_access_token
    from apps.accounts.models import Member

    # Get member to find Stytch IDs (query all memberships, not just current)
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
