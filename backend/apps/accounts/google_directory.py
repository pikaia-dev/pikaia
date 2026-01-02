"""
Google Directory API client for searching workspace users.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from django.conf import settings

from apps.accounts.models import User

logger = logging.getLogger(__name__)

# Google OAuth endpoints
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DIRECTORY_API_URL = "https://admin.googleapis.com/admin/directory/v1"


@dataclass
class DirectoryUser:
    """A user from Google Workspace directory."""

    email: str
    name: str
    avatar_url: str = ""


def refresh_google_token(user: User) -> str | None:
    """
    Refresh the user's Google access token if expired.

    Returns the valid access token or None if refresh fails.
    """
    if not user.google_refresh_token:
        return None

    # Check if token is still valid (with 5 minute buffer)
    if user.google_token_expires_at and user.google_token_expires_at > datetime.now(
        UTC
    ) + timedelta(minutes=5):
        return user.google_access_token

    # Refresh the token
    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "refresh_token": user.google_refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        # Update user tokens
        user.google_access_token = data["access_token"]
        user.google_token_expires_at = datetime.now(UTC) + timedelta(
            seconds=data.get("expires_in", 3600)
        )
        user.save(update_fields=["google_access_token", "google_token_expires_at"])

        return user.google_access_token
    except httpx.HTTPError as e:
        logger.warning("Failed to refresh Google token for user %s: %s", user.email, e)
        return None


def search_directory_users(user: User, query: str, limit: int = 10) -> list[DirectoryUser]:
    """
    Search Google Workspace directory for users matching query.

    Args:
        user: The authenticated user (must have Directory API tokens)
        query: Search query (matches name or email)
        limit: Maximum results to return

    Returns:
        List of matching DirectoryUser objects
    """
    access_token = refresh_google_token(user)
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
            # User doesn't have admin access to directory
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


def store_google_tokens(
    user: User,
    access_token: str,
    refresh_token: str | None,
    expires_in: int,
) -> None:
    """
    Store Google OAuth tokens for a user.

    Called after successful OAuth authentication.
    """
    user.google_access_token = access_token
    if refresh_token:
        user.google_refresh_token = refresh_token
    user.google_token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    update_fields = ["google_access_token", "google_token_expires_at"]
    if refresh_token:
        update_fields.append("google_refresh_token")

    user.save(update_fields=update_fields)
