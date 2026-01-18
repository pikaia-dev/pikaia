"""
Auth services - business logic for authentication.

Handles sync between Stytch and local User/Member/Organization models.
"""

from typing import Any

from django.db import IntegrityError, transaction

from apps.accounts.constants import StytchRoles
from apps.accounts.models import Member, User
from apps.core.logging import get_logger
from apps.organizations.models import Organization

logger = get_logger(__name__)


def get_or_create_user_from_stytch(
    email: str,
    name: str = "",
    avatar_url: str = "",
) -> User:
    """
    Get or create a User from Stytch data.

    Email is the cross-org identifier in Stytch B2B.
    Called during authentication to sync user data.

    Args:
        email: User's email address
        name: User's display name
        avatar_url: User's profile picture URL (e.g., from Google OAuth)

    Uses select_for_update for explicit row locking under concurrent requests.
    """
    try:
        user = User.objects.select_for_update().get(email=email)
        update_fields = ["updated_at"]
        # Only update name if provided and user doesn't have one
        # This preserves existing names when user joins additional orgs
        if name and not user.name:
            user.name = name
            update_fields.append("name")
        # Only update avatar if provided and user doesn't have one
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
            update_fields.append("avatar_url")
        user.save(update_fields=update_fields)
        return user
    except User.DoesNotExist:
        try:
            return User.objects.create(email=email, name=name, avatar_url=avatar_url)
        except IntegrityError:
            # Concurrent insert won the race, fetch the winner
            return User.objects.get(email=email)


def get_or_create_organization_from_stytch(
    stytch_org_id: str,
    name: str,
    slug: str,
) -> Organization:
    """
    Get or create an Organization from Stytch data.

    Called during org creation or when user joins an org.

    Uses select_for_update for explicit row locking under concurrent requests.
    """
    try:
        org = Organization.objects.select_for_update().get(stytch_org_id=stytch_org_id)
        org.name = name
        org.slug = slug
        org.save(update_fields=["name", "slug", "updated_at"])
        return org
    except Organization.DoesNotExist:
        try:
            return Organization.objects.create(
                stytch_org_id=stytch_org_id,
                name=name,
                slug=slug,
            )
        except IntegrityError:
            # Concurrent insert won the race, fetch the winner
            return Organization.objects.get(stytch_org_id=stytch_org_id)


def get_or_create_member_from_stytch(
    user: User,
    organization: Organization,
    stytch_member_id: str,
    role: str = "member",
) -> Member:
    """
    Get or create a Member linking User to Organization.

    Called during authentication after org selection.

    Uses select_for_update for explicit row locking under concurrent requests.
    """
    try:
        member = Member.objects.select_for_update().get(stytch_member_id=stytch_member_id)
        member.user = user
        member.organization = organization
        member.role = role
        member.save(update_fields=["user", "organization", "role", "updated_at"])
        return member
    except Member.DoesNotExist:
        try:
            return Member.objects.create(
                stytch_member_id=stytch_member_id,
                user=user,
                organization=organization,
                role=role,
            )
        except IntegrityError:
            # Concurrent insert won the race, fetch the winner
            return Member.objects.get(stytch_member_id=stytch_member_id)


def sync_session_to_local(
    stytch_member: Any,  # Stytch Member object from SDK
    stytch_organization: Any,  # Stytch Organization object from SDK
) -> tuple[User, Member, Organization]:
    """
    Sync Stytch session data to local models.

    Called after successful authentication to ensure local
    User, Member, and Organization records exist.

    This function is idempotent and concurrency-safe:
    - Uses transaction.atomic() for all-or-nothing semantics
    - Uses select_for_update() for explicit row locking
    - Falls back to IntegrityError handling for race conditions

    Returns:
        Tuple of (user, member, organization)
    """
    with transaction.atomic():
        # Sync organization
        org = get_or_create_organization_from_stytch(
            stytch_org_id=stytch_organization.organization_id,
            name=stytch_organization.organization_name,
            slug=stytch_organization.organization_slug,
        )

        # Sync user - email is the cross-org identifier
        # profile_picture_url is set when user logs in via Google OAuth
        user = get_or_create_user_from_stytch(
            email=stytch_member.email_address,
            name=stytch_member.name or "",
            avatar_url=getattr(stytch_member, "profile_picture_url", "") or "",
        )

        # Determine role from Stytch RBAC
        # member.roles is an array of role objects with role_id field
        # e.g. [{"role_id": "stytch_admin", "sources": [...]}, ...]
        # See StytchRoles for valid role IDs
        roles = getattr(stytch_member, "roles", []) or []
        role_ids = [
            getattr(r, "role_id", None) or r.get("role_id")
            if hasattr(r, "get")
            else getattr(r, "role_id", None)
            for r in roles
        ]
        role = "admin" if StytchRoles.ADMIN in role_ids else "member"

        # Sync member
        member = get_or_create_member_from_stytch(
            user=user,
            organization=org,
            stytch_member_id=stytch_member.member_id,
            role=role,
        )

    return user, member, org


# --- Member Management Services ---


def list_organization_members(organization: Organization) -> list[Member]:
    """
    List all active members of an organization.

    Uses select_related to avoid N+1 queries.

    Returns:
        List of active (non-deleted) Member objects.
    """
    return list(
        Member.objects.filter(organization=organization)
        .select_related("user")
        .order_by("created_at")
    )


def invite_member(
    organization: Organization,
    email: str,
    name: str = "",
    role: str = "member",
) -> tuple[Member, bool | str]:
    """
    Invite a new member to the organization via Stytch.

    Creates the member in Stytch which sends an invite email with Magic Link.
    Then syncs to local database. If the user was previously removed,
    reactivates their membership in both Stytch and local database.

    Args:
        organization: The organization to invite to
        email: Email address of the member to invite
        name: Optional display name
        role: Role to assign ('admin' or 'member')

    Returns:
        Tuple of (Member object, invite_status: True if sent, False if active, 'pending' if already invited)

    Raises:
        StytchError: If Stytch API call fails (other than duplicate_email)
    """
    from stytch.core.response_base import StytchError

    from apps.accounts.stytch_client import get_stytch_client

    stytch = get_stytch_client()

    # Normalize email to prevent search mismatches
    email = email.strip().lower()

    # Map role to Stytch role IDs
    roles = [StytchRoles.ADMIN] if role == "admin" else []

    stytch_member_id = None
    invite_sent: bool | str = False

    # First, check if member already exists in Stytch
    search_result = stytch.organizations.members.search(
        organization_ids=[organization.stytch_org_id],
        query={
            "operator": "AND",
            "operands": [{"filter_name": "member_emails", "filter_value": [email]}],
        },
    )

    if search_result.members:
        # Member already exists - check their status
        existing_member = search_result.members[0]
        stytch_member_id = existing_member.member_id
        member_status = getattr(existing_member, "status", "active")

        if member_status == "deleted":
            # Reactivate deleted member and send invite
            stytch.organizations.members.reactivate(
                organization_id=organization.stytch_org_id,
                member_id=stytch_member_id,
            )
            try:
                stytch.magic_links.email.invite(
                    organization_id=organization.stytch_org_id,
                    email_address=email,
                )
                invite_sent = True
            except StytchError:
                invite_sent = True  # Reactivated even if email failed
        elif member_status == "invited":
            # Already invited, don't resend
            invite_sent = "pending"
        else:
            # Active member
            invite_sent = False

        # Update their role and name
        stytch.organizations.members.update(
            organization_id=organization.stytch_org_id,
            member_id=stytch_member_id,
            name=name if name else None,
            roles=roles,
        )
    else:
        # New member - send invite (creates member AND sends email)
        result = stytch.magic_links.email.invite(
            organization_id=organization.stytch_org_id,
            email_address=email,
        )
        stytch_member_id = result.member_id
        invite_sent = True

        # Update role/name if specified (invite doesn't set these)
        if name or roles:
            stytch.organizations.members.update(
                organization_id=organization.stytch_org_id,
                member_id=stytch_member_id,
                name=name if name else None,
                roles=roles,
            )

    # Sync to local database - wrapped in transaction for select_for_update
    with transaction.atomic():
        user = get_or_create_user_from_stytch(email=email, name=name)

        # Check if this user was previously a member (soft-deleted)
        # Use all_objects to include soft-deleted members
        existing_member = Member.all_objects.filter(user=user, organization=organization).first()

        if existing_member:
            # Reactivate the soft-deleted member with new Stytch ID
            existing_member.stytch_member_id = stytch_member_id
            existing_member.role = role
            existing_member.deleted_at = None  # Reactivate
            existing_member.save(
                update_fields=["stytch_member_id", "role", "deleted_at", "updated_at"]
            )
            member = existing_member
        else:
            # Create new member
            member = get_or_create_member_from_stytch(
                user=user,
                organization=organization,
                stytch_member_id=stytch_member_id,
                role=role,
            )

    # Sync subscription quantity to Stripe (outside transaction - external call)
    _sync_subscription_quantity_safe(organization)

    return member, invite_sent


def update_member_role(
    member: Member,
    role: str,
) -> Member:
    """
    Update a member's role locally and sync to Stytch.

    Args:
        member: The Member to update
        role: New role ('admin' or 'member')

    Returns:
        The updated Member object
    """
    from apps.accounts.stytch_client import get_stytch_client

    stytch = get_stytch_client()

    # Map role to Stytch role IDs
    roles = [StytchRoles.ADMIN] if role == "admin" else []

    # Update in Stytch
    stytch.organizations.members.update(
        organization_id=member.organization.stytch_org_id,
        member_id=member.stytch_member_id,
        roles=roles,
    )

    # Update locally
    member.role = role
    member.save(update_fields=["role", "updated_at"])

    return member


def soft_delete_member(member: Member) -> None:
    """
    Soft delete a member locally and delete from Stytch.

    The member is marked as deleted locally (deleted_at set) and
    removed from Stytch so they can no longer authenticate.

    Uses transaction.atomic() with select_for_update() to prevent
    concurrent deletion race conditions.

    Args:
        member: The Member to delete
    """
    from apps.accounts.stytch_client import get_stytch_client

    stytch = get_stytch_client()
    organization = member.organization

    # Delete from Stytch first (prevents login)
    stytch.organizations.members.delete(
        organization_id=organization.stytch_org_id,
        member_id=member.stytch_member_id,
    )

    # Soft delete locally with row lock to prevent concurrent updates
    with transaction.atomic():
        locked_member = Member.all_objects.select_for_update().get(pk=member.pk)
        if not locked_member.is_deleted:
            locked_member.soft_delete()

    # Sync subscription quantity to Stripe (outside transaction - external call)
    _sync_subscription_quantity_safe(organization)


def _sync_subscription_quantity_safe(organization: Organization) -> None:
    """
    Sync subscription quantity to Stripe, logging failures without raising.

    This is called after member changes (invite/delete) to update the
    per-seat subscription quantity. Failures are logged but don't fail
    the parent operation.
    """
    try:
        from apps.billing.services import sync_subscription_quantity

        sync_subscription_quantity(organization)
    except Exception:
        logger.warning("billing_subscription_quantity_sync_failed", org_id=str(organization.id))


def sync_logo_to_stytch(organization: Organization) -> None:
    """
    Sync organization logo URL to Stytch.

    Called after logo upload/delete in media API.
    Fails silently with a warning log on error to not break the upload flow.
    """
    from stytch.core.response_base import StytchError

    from apps.accounts.stytch_client import get_stytch_client

    try:
        client = get_stytch_client()
        client.organizations.update(
            organization_id=organization.stytch_org_id,
            organization_logo_url=organization.logo_url,
        )
    except StytchError as e:
        logger.warning(
            "stytch_logo_sync_failed",
            stytch_org_id=organization.stytch_org_id,
            error=e.details.error_message,
        )


# --- Bulk Invite Services ---

# Maximum members allowed in a single bulk invite (enforced at schema level too)
MAX_BULK_INVITE_SIZE = 100


def bulk_invite_members(
    organization: Organization,
    members_data: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Invite multiple members to the organization at once.

    Processes each member individually, catching errors per-row to allow
    partial success. Phone numbers are stored unverified on the User model
    (will require OTP verification later).

    Deduplicates emails (case-insensitive) - only the first occurrence is processed.

    Args:
        organization: The organization to invite to
        members_data: List of dicts with keys: email, name, phone, role

    Returns:
        Dict with results, total, succeeded, failed counts

    Raises:
        ValueError: If members_data exceeds MAX_BULK_INVITE_SIZE
    """
    import logging

    from stytch.core.response_base import StytchError

    if len(members_data) > MAX_BULK_INVITE_SIZE:
        raise ValueError(f"Bulk invite limited to {MAX_BULK_INVITE_SIZE} members")

    logger = logging.getLogger(__name__)
    results = []
    succeeded = 0
    failed = 0

    # Dedupe emails (case-insensitive), keeping first occurrence
    seen_emails: set[str] = set()
    unique_members_data = []
    for member_item in members_data:
        email_lower = member_item.get("email", "").lower()
        if email_lower in seen_emails:
            # Skip duplicate, report as failed
            results.append(
                {
                    "email": member_item.get("email", ""),
                    "success": False,
                    "error": "Duplicate email in request",
                    "stytch_member_id": None,
                }
            )
            failed += 1
            continue
        seen_emails.add(email_lower)
        unique_members_data.append(member_item)

    for member_item in unique_members_data:
        email = member_item.get("email", "")
        name = member_item.get("name", "")
        phone = member_item.get("phone", "")
        role = member_item.get("role", "member")

        try:
            member, invite_status = invite_member(
                organization=organization,
                email=email,
                name=name,
                role=role,
            )

            # Store phone number (unverified) on the User if provided
            if phone:
                user = member.user
                # Only update phone if user doesn't have one or it's different
                if not user.phone_number or user.phone_number != phone:
                    user.phone_number = phone
                    user.phone_verified_at = None  # Explicitly mark as unverified
                    user.save(update_fields=["phone_number", "phone_verified_at", "updated_at"])

            # Provide informative feedback based on invite status
            if invite_status is False:
                # Member already active - not an error, but no invite sent
                results.append(
                    {
                        "email": email,
                        "success": False,
                        "error": "Member already active in this organization",
                        "stytch_member_id": member.stytch_member_id,
                    }
                )
                failed += 1
            elif invite_status == "pending":
                # Member already invited - not an error, but no new invite sent
                results.append(
                    {
                        "email": email,
                        "success": False,
                        "error": "Member already has a pending invitation",
                        "stytch_member_id": member.stytch_member_id,
                    }
                )
                failed += 1
            else:
                # New invite sent successfully
                results.append(
                    {
                        "email": email,
                        "success": True,
                        "error": None,
                        "stytch_member_id": member.stytch_member_id,
                    }
                )
                succeeded += 1

        except StytchError as e:
            error_msg = e.details.error_message if e.details else str(e)
            logger.warning(
                "Bulk invite failed for %s: %s",
                email,
                error_msg,
            )
            results.append(
                {
                    "email": email,
                    "success": False,
                    "error": error_msg,
                    "stytch_member_id": None,
                }
            )
            failed += 1

        except Exception as e:
            logger.exception("Unexpected error inviting %s", email)
            results.append(
                {
                    "email": email,
                    "success": False,
                    "error": str(e),
                    "stytch_member_id": None,
                }
            )
            failed += 1

    return {
        "results": results,
        "total": len(members_data),
        "succeeded": succeeded,
        "failed": failed,
    }


# --- Mobile Provisioning Services ---


def provision_mobile_user(
    email: str,
    name: str = "",
    phone_number: str = "",
    organization_id: str | None = None,
    organization_name: str | None = None,
    organization_slug: str | None = None,
) -> tuple[User, Member, Organization, str, str]:
    """
    Provision a mobile user and create a Stytch session via Trusted Auth.

    Either joins an existing org (organization_id) or creates a new one
    (organization_name + organization_slug).

    Args:
        email: User's email address
        name: User's display name (optional)
        phone_number: User's phone number in E.164 format (optional, stored unverified)
        organization_id: Stytch org ID to join existing org
        organization_name: Name for new organization (requires organization_slug)
        organization_slug: Slug for new organization (requires organization_name)

    Returns:
        Tuple of (user, member, org, session_token, session_jwt)

    Raises:
        ValueError: If input validation fails
        StytchError: If Stytch API call fails
    """
    from django.conf import settings as django_settings

    from apps.accounts.stytch_client import get_stytch_client
    from apps.passkeys.trusted_auth import create_trusted_auth_token

    # Input validation
    email = email.strip().lower()
    creating_org = organization_name is not None or organization_slug is not None
    joining_org = organization_id is not None

    if creating_org and joining_org:
        raise ValueError("Cannot specify both organization_id and organization_name/slug")

    if not creating_org and not joining_org:
        raise ValueError(
            "Must specify either organization_id or organization_name and organization_slug"
        )

    if creating_org and (not organization_name or not organization_slug):
        raise ValueError(
            "Both organization_name and organization_slug are required to create an organization"
        )

    stytch = get_stytch_client()
    stytch_org_id: str
    stytch_member_id: str
    stytch_member: Any  # Stytch Member object
    stytch_organization: Any  # Stytch Organization object

    if creating_org:
        # Create new organization
        org_response = stytch.organizations.create(
            organization_name=organization_name,
            organization_slug=organization_slug,
        )
        stytch_org_id = org_response.organization.organization_id
        stytch_organization = org_response.organization

        # Create member in the new org
        member_response = stytch.organizations.members.create(
            organization_id=stytch_org_id,
            email_address=email,
            name=name if name else None,
        )
        stytch_member_id = member_response.member.member_id
        stytch_member = member_response.member

        # Make the creator an admin
        stytch.organizations.members.update(
            organization_id=stytch_org_id,
            member_id=stytch_member_id,
            roles=[StytchRoles.ADMIN],
        )
    else:
        # Join existing organization
        stytch_org_id = organization_id  # type: ignore[assignment]

        # Get org details
        org_response = stytch.organizations.get(organization_id=stytch_org_id)
        stytch_organization = org_response.organization

        # Check if member already exists
        search_result = stytch.organizations.members.search(
            organization_ids=[stytch_org_id],
            query={
                "operator": "AND",
                "operands": [{"filter_name": "member_emails", "filter_value": [email]}],
            },
        )

        if search_result.members:
            existing_member = search_result.members[0]
            member_status = getattr(existing_member, "status", "active")

            if member_status == "deleted":
                # Reactivate deleted member
                stytch.organizations.members.reactivate(
                    organization_id=stytch_org_id,
                    member_id=existing_member.member_id,
                )

            stytch_member_id = existing_member.member_id

            # Update name if provided
            if name:
                stytch.organizations.members.update(
                    organization_id=stytch_org_id,
                    member_id=stytch_member_id,
                    name=name,
                )

            # Fetch updated member
            member_response = stytch.organizations.members.get(
                organization_id=stytch_org_id,
                member_id=stytch_member_id,
            )
            stytch_member = member_response.member
        else:
            # Create new member
            member_response = stytch.organizations.members.create(
                organization_id=stytch_org_id,
                email_address=email,
                name=name if name else None,
            )
            stytch_member_id = member_response.member.member_id
            stytch_member = member_response.member

    # Sync to local database
    user, member, org = sync_session_to_local(
        stytch_member=stytch_member,
        stytch_organization=stytch_organization,
    )

    # Store phone number if provided (unverified)
    if phone_number:
        user.phone_number = phone_number
        user.phone_verified_at = None
        user.save(update_fields=["phone_number", "phone_verified_at", "updated_at"])

    # Create trusted auth token for session attestation
    trusted_token = create_trusted_auth_token(
        email=user.email,
        member_id=stytch_member_id,
        organization_id=stytch_org_id,
        user_id=user.id,
    )

    # Exchange for real Stytch session
    attest_response = stytch.sessions.attest(
        profile_id=django_settings.STYTCH_TRUSTED_AUTH_PROFILE_ID,
        token=trusted_token,
        organization_id=stytch_org_id,
        session_duration_minutes=43200,  # 30 days
    )

    return user, member, org, attest_response.session_token, attest_response.session_jwt
