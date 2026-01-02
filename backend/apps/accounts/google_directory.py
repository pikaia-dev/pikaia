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
        return response.access_token
    except StytchError as e:
        # No Google OAuth tokens for this member
        logger.debug(
            "No Google OAuth tokens for member %s: %s",
            member_id,
            e.details.error_message if e.details else str(e),
        )
        return None


def search_directory_users(
    user: "User",  # noqa: F821 - forward reference
    query: str,
    limit: int = 10,
) -> list[DirectoryUser]:
    """
    Search Google Workspace directory for users matching query.

    Args:
        user: The authenticated user (must have Google OAuth)
        query: Search query (matches name or email)
        limit: Maximum results to return

    Returns:
        List of matching DirectoryUser objects
    """
    # Import here to avoid circular imports
    from apps.accounts.models import Member

    # Find the member for this user to get Stytch IDs
    member = (
        Member.objects.filter(user=user, deleted_at__isnull=True)
        .select_related("organization")
        .first()
    )

    if not member:
        return []

    access_token = get_google_access_token(
        organization_id=member.organization.stytch_org_id,
        member_id=member.stytch_member_id,
    )

    if not access_token:
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
            logger.debug(
                "User %s doesn't have Directory API access (403)", user.email
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
