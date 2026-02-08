"""
Generic OAuth provider abstraction.

Retrieves OAuth tokens from Stytch for any supported provider.
Stytch stores and auto-refreshes tokens - no local token storage needed.
"""

from enum import StrEnum

from stytch.core.response_base import StytchError

from apps.accounts.stytch_client import get_stytch_client
from apps.core.logging import get_logger

logger = get_logger(__name__)


class OAuthProvider(StrEnum):
    """Supported OAuth providers matching Stytch SDK method names."""

    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"


def get_oauth_token(provider: OAuthProvider, organization_id: str, member_id: str) -> str | None:
    """
    Get OAuth access token from Stytch for a member and provider.

    Stytch stores and auto-refreshes OAuth tokens.
    Returns None if no tokens are available for the given provider.

    Args:
        provider: The OAuth provider to get a token for
        organization_id: Stytch organization ID
        member_id: Stytch member ID

    Returns:
        Access token string, or None if unavailable
    """
    try:
        client = get_stytch_client()
        provider_method = getattr(
            client.organizations.members.oauth_providers, provider.value, None
        )
        if provider_method is None:
            logger.warning(
                "stytch_oauth_provider_not_available",
                provider=provider.value,
            )
            return None
        response = provider_method(
            organization_id=organization_id,
            member_id=member_id,
        )

        # Google returns access_token directly on the response.
        # GitHub/Microsoft return a registrations list with access_tokens.
        token: str | None = None
        if hasattr(response, "access_token"):
            token = str(response.access_token) if response.access_token else None
        elif hasattr(response, "registrations") and response.registrations:
            raw = response.registrations[0].access_token
            token = str(raw) if raw else None

        if not token:
            logger.warning(
                "stytch_oauth_no_token",
                provider=provider.value,
                member_id=member_id,
                organization_id=organization_id,
            )

        return token

    except StytchError as e:
        error_message = e.details.error_message if e.details else str(e)
        logger.debug(
            "oauth_token_not_found",
            provider=provider.value,
            member_id=member_id,
            error=error_message,
        )
        return None
