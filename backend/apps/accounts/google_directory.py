"""
Google Directory API client for searching workspace users.

Uses Stytch's stored OAuth tokens - no local token storage needed.
Stytch automatically refreshes tokens when calling their API.
"""

import logging
from dataclasses import dataclass

import httpx
from stytch.core.response_base import StytchError

from apps.accounts.stytch_client import get_stytch_client

logger = logging.getLogger(__name__)

# Google Directory API endpoint
GOOGLE_DIRECTORY_API_URL = "https://admin.googleapis.com/admin/directory/v1"


@dataclass
class DirectoryUser:
    """A user from Google Workspace directory."""

    email: str
    name: str
    avatar_url: str = ""


def get_google_access_token(organization_id: str, member_id: str) -> str | None:
    """
    Get Google access token from Stytch for a member.

    Stytch stores and auto-refreshes Google OAuth tokens.
    Returns None if no Google OAuth tokens are available.
    """
    try:
        client = get_stytch_client()
        response = client.organizations.members.oauth_providers.google(
            organization_id=organization_id,
            member_id=member_id,
        )
        # access_token is directly on the response (Optional field)
        if not response.access_token:
            logger.warning(
                "Stytch returned no access_token for member %s (org %s)",
                member_id,
                organization_id,
            )
        return response.access_token
    except StytchError as e:
        # No Google OAuth tokens for this member
        logger.warning(
            "No Google OAuth tokens for member %s: %s",
            member_id,
            e.details.error_message if e.details else str(e),
        )
        return None


def search_directory_users(
    user: "User",  # noqa: F821 - forward reference
    member: "Member",  # noqa: F821 - forward reference
    query: str,
    limit: int = 10,
) -> list[DirectoryUser]:
    """
    Search Google Workspace directory for users matching query.

    Args:
        user: The authenticated user
        member: The current member (tried first for Google token)
        query: Search query (matches name or email)
        limit: Maximum results to return

    Returns:
        List of matching DirectoryUser objects
    """
    # Import here to avoid circular imports
    from apps.accounts.models import Member

    # Try current member first, then fall back to any member with a Google token
    # (user may have logged in via Google in a different org)
    access_token = get_google_access_token(
        organization_id=member.organization.stytch_org_id,
        member_id=member.stytch_member_id,
    )

    if not access_token:
        # Try other memberships (ordered by oldest first - most likely to have token)
        other_members = (
            Member.objects.filter(user=user, deleted_at__isnull=True)
            .exclude(id=member.id)
            .select_related("organization")
            .order_by("created_at")
        )
        for other_member in other_members:
            access_token = get_google_access_token(
                organization_id=other_member.organization.stytch_org_id,
                member_id=other_member.stytch_member_id,
            )
            if access_token:
                logger.info(
                    "Directory search: using token from member %s (org %s) for user %s",
                    other_member.stytch_member_id,
                    other_member.organization.name,
                    user.email,
                )
                break

    if not access_token:
        logger.warning(
            "Directory search: no Google OAuth token found for user %s in any org",
            user.email,
        )
        return []

    try:
        # Get user's domain from email
        domain = user.email.split("@")[1] if "@" in user.email else None
        if not domain:
            return []

        response = httpx.get(
            f"{GOOGLE_DIRECTORY_API_URL}/users",
            params={
                "domain": domain,
                "query": query,
                "maxResults": limit,
                "orderBy": "email",
                "viewType": "domain_public",
            },
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )

        if response.status_code == 403:
            # User doesn't have admin access to directory or scope not granted
            logger.warning(
                "Directory API returned 403 for user %s - check scopes or Workspace settings",
                user.email,
            )
            return []

        response.raise_for_status()
        data = response.json()

        users = []
        for u in data.get("users", []):
            primary_email = u.get("primaryEmail", "")
            full_name = u.get("name", {}).get("fullName", "")
            # thumbnailPhotoUrl requires OAuth auth - frontend will use our proxy
            photo_url = u.get("thumbnailPhotoUrl", "")

            users.append(
                DirectoryUser(
                    email=primary_email,
                    name=full_name,
                    avatar_url=photo_url,
                )
            )

        return users

    except httpx.HTTPError as e:
        logger.warning("Directory API search failed for user %s: %s", user.email, e)
        return []
