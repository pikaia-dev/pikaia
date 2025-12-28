"""
Auth services - business logic for authentication.

Handles sync between Stytch and local User/Member/Organization models.
"""

from typing import Any

from django.db import transaction

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
    """
    user, created = User.objects.update_or_create(
        email=email,
        defaults={"name": name},
    )
    return user


def get_or_create_organization_from_stytch(
    stytch_org_id: str,
    name: str,
    slug: str,
) -> Organization:
    """
    Get or create an Organization from Stytch data.

    Called during org creation or when user joins an org.
    """
    org, created = Organization.objects.update_or_create(
        stytch_org_id=stytch_org_id,
        defaults={
            "name": name,
            "slug": slug,
        },
    )
    return org


def get_or_create_member_from_stytch(
    user: User,
    organization: Organization,
    stytch_member_id: str,
    role: str = "member",
) -> Member:
    """
    Get or create a Member linking User to Organization.

    Called during authentication after org selection.
    """
    member, created = Member.objects.update_or_create(
        stytch_member_id=stytch_member_id,
        defaults={
            "user": user,
            "organization": organization,
            "role": role,
        },
    )
    return member


def sync_session_to_local(
    stytch_member: Any,  # Stytch Member object from SDK
    stytch_organization: Any,  # Stytch Organization object from SDK
) -> tuple[User, Member, Organization]:
    """
    Sync Stytch session data to local models.

    Called after successful authentication to ensure local
    User, Member, and Organization records exist.

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

        # Determine role from Stytch RBAC (simplified)
        # In full implementation, parse stytch_member.roles
        role = "admin" if "stytch_admin" in getattr(stytch_member, "roles", []) else "member"

        # Sync member
        member = get_or_create_member_from_stytch(
            user=user,
            organization=org,
            stytch_member_id=stytch_member.member_id,
            role=role,
        )

    return user, member, org
