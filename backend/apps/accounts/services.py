"""
Auth services - business logic for authentication.

Handles sync between Stytch and local User/Member/Organization models.
"""

from typing import Any

from django.db import IntegrityError, transaction

from apps.accounts.constants import StytchRoles
from apps.accounts.models import Member, User
from apps.organizations.models import Organization


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
        user.name = name
        update_fields = ["name", "updated_at"]
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
            getattr(r, "role_id", None) or r.get("role_id") if hasattr(r, "get") else getattr(r, "role_id", None)
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

    # Map role to Stytch role IDs
    roles = [StytchRoles.ADMIN] if role == "admin" else []

    stytch_member_id = None
    invite_sent: bool | str = False

    # First, check if member already exists in Stytch
    search_result = stytch.organizations.members.search(
        organization_ids=[organization.stytch_org_id],
        query={
            "operator": "AND",
            "operands": [
                {"filter_name": "member_emails", "filter_value": [email]}
            ],
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
        existing_member = Member.all_objects.filter(
            user=user, organization=organization
        ).first()

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
    try:
        from apps.billing.services import sync_subscription_quantity

        sync_subscription_quantity(organization)
    except Exception:
        # Don't fail the invite if billing sync fails
        import logging

        logging.getLogger(__name__).warning(
            "Failed to sync subscription quantity for org %s", organization.id
        )

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

    # Soft delete locally
    member.soft_delete()

    # Sync subscription quantity to Stripe (outside transaction - external call)
    try:
        from apps.billing.services import sync_subscription_quantity

        sync_subscription_quantity(organization)
    except Exception:
        # Don't fail the delete if billing sync fails
        import logging

        logging.getLogger(__name__).warning(
            "Failed to sync subscription quantity for org %s", organization.id
        )


def sync_logo_to_stytch(organization: Organization) -> None:
    """
    Sync organization logo URL to Stytch.

    Called after logo upload/delete in media API.
    Fails silently with a warning log on error to not break the upload flow.
    """
    import logging

    from stytch.core.response_base import StytchError

    from apps.accounts.stytch_client import get_stytch_client

    logger = logging.getLogger(__name__)

    try:
        client = get_stytch_client()
        client.organizations.update(
            organization_id=organization.stytch_org_id,
            organization_logo_url=organization.logo_url,
        )
    except StytchError as e:
        logger.warning(
            "Failed to sync logo to Stytch for org %s: %s",
            organization.stytch_org_id,
            e.details.error_message,
        )
