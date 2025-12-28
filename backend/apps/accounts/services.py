"""
Auth services - business logic for authentication.

Handles sync between Stytch and local User/Member/Organization models.
"""

from typing import Any

from django.db import IntegrityError, transaction

from apps.accounts.models import Member, User
from apps.organizations.models import Organization


def get_or_create_user_from_stytch(
    email: str,
    name: str = "",
) -> User:
    """
    Get or create a User from Stytch data.

    Email is the cross-org identifier in Stytch B2B.
    Called during authentication to sync user data.

    Uses select_for_update for explicit row locking under concurrent requests.
    """
    try:
        user = User.objects.select_for_update().get(email=email)
        user.name = name
        user.save(update_fields=["name", "updated_at"])
        return user
    except User.DoesNotExist:
        try:
            return User.objects.create(email=email, name=name)
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
        user = get_or_create_user_from_stytch(
            email=stytch_member.email_address,
            name=stytch_member.name or "",
        )

        # Determine role from Stytch RBAC
        # member.roles is an array of role objects with role_id field
        # e.g. [{"role_id": "stytch_admin", "sources": [...]}, ...]
        roles = getattr(stytch_member, "roles", []) or []
        role_ids = [
            getattr(r, "role_id", None) or r.get("role_id") if hasattr(r, "get") else getattr(r, "role_id", None)
            for r in roles
        ]
        role = "admin" if "stytch_admin" in role_ids else "member"

        # Sync member
        member = get_or_create_member_from_stytch(
            user=user,
            organization=org,
            stytch_member_id=stytch_member.member_id,
            role=role,
        )

    return user, member, org

