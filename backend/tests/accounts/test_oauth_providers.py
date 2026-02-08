"""
Tests for generic OAuth provider token retrieval.
"""

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

from stytch.core.response_base import StytchError, StytchErrorDetails

from apps.accounts.oauth_providers import OAuthProvider, get_oauth_token


@dataclass
class MockGoogleOAuthResponse:
    """Mock Stytch Google OAuth response (flat access_token)."""

    access_token: str | None


@dataclass
class MockRegistration:
    """Mock Stytch OAuth registration entry."""

    access_token: str | None


@dataclass
class MockGitHubOAuthResponse:
    """Mock Stytch GitHub OAuth response (registrations list)."""

    registrations: list[MockRegistration] = field(default_factory=list)


class TestGetOAuthToken:
    """Tests for get_oauth_token function."""

    @patch("apps.accounts.oauth_providers.get_stytch_client")
    def test_returns_google_token(self, mock_get_client: MagicMock) -> None:
        """Should return access token for Google (flat response)."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.google.return_value = (
            MockGoogleOAuthResponse(access_token="google-token-123")
        )
        mock_get_client.return_value = mock_client

        result = get_oauth_token(OAuthProvider.GOOGLE, "org-123", "member-456")

        assert result == "google-token-123"
        mock_client.organizations.members.oauth_providers.google.assert_called_once_with(
            organization_id="org-123",
            member_id="member-456",
        )

    @patch("apps.accounts.oauth_providers.get_stytch_client")
    def test_returns_github_token_from_registrations(self, mock_get_client: MagicMock) -> None:
        """Should return access token from registrations list (GitHub-style)."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.github.return_value = (
            MockGitHubOAuthResponse(
                registrations=[MockRegistration(access_token="github-token-789")]
            )
        )
        mock_get_client.return_value = mock_client

        result = get_oauth_token(OAuthProvider.GITHUB, "org-123", "member-456")

        assert result == "github-token-789"

    @patch("apps.accounts.oauth_providers.get_stytch_client")
    def test_returns_none_on_stytch_error(self, mock_get_client: MagicMock) -> None:
        """Should return None when Stytch returns an error."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.google.side_effect = StytchError(
            StytchErrorDetails(
                status_code=404,
                request_id="req-123",
                error_type="member_not_found",
                error_message="No OAuth tokens for this member",
            )
        )
        mock_get_client.return_value = mock_client

        result = get_oauth_token(OAuthProvider.GOOGLE, "org-123", "member-789")

        assert result is None

    @patch("apps.accounts.oauth_providers.get_stytch_client")
    def test_returns_none_when_token_is_none(self, mock_get_client: MagicMock) -> None:
        """Should return None when Stytch returns no access token."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.google.return_value = (
            MockGoogleOAuthResponse(access_token=None)
        )
        mock_get_client.return_value = mock_client

        result = get_oauth_token(OAuthProvider.GOOGLE, "org-123", "member-456")

        assert result is None

    @patch("apps.accounts.oauth_providers.get_stytch_client")
    def test_returns_none_when_registrations_empty(self, mock_get_client: MagicMock) -> None:
        """Should return None when registrations list is empty."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.github.return_value = (
            MockGitHubOAuthResponse(registrations=[])
        )
        mock_get_client.return_value = mock_client

        result = get_oauth_token(OAuthProvider.GITHUB, "org-123", "member-456")

        assert result is None

    @patch("apps.accounts.oauth_providers.get_stytch_client")
    def test_returns_none_when_provider_not_available(self, mock_get_client: MagicMock) -> None:
        """Should return None when provider method is missing from Stytch client."""
        mock_client = MagicMock()
        # Simulate provider method not existing on the SDK
        mock_client.organizations.members.oauth_providers = MagicMock(spec=[])
        mock_get_client.return_value = mock_client

        result = get_oauth_token(OAuthProvider.GOOGLE, "org-123", "member-456")

        assert result is None

    @patch("apps.accounts.oauth_providers.get_stytch_client")
    def test_dispatches_to_correct_provider_method(self, mock_get_client: MagicMock) -> None:
        """Should call the correct provider method on the Stytch client."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.microsoft.return_value = (
            MockGitHubOAuthResponse(registrations=[MockRegistration(access_token="ms-token")])
        )
        mock_get_client.return_value = mock_client

        result = get_oauth_token(OAuthProvider.MICROSOFT, "org-1", "member-1")

        assert result == "ms-token"
        mock_client.organizations.members.oauth_providers.microsoft.assert_called_once_with(
            organization_id="org-1",
            member_id="member-1",
        )


class TestOAuthProviderEnum:
    """Tests for OAuthProvider enum."""

    def test_values_match_stytch_method_names(self) -> None:
        """Provider values should match Stytch SDK method names."""
        assert OAuthProvider.GOOGLE.value == "google"
        assert OAuthProvider.GITHUB.value == "github"
        assert OAuthProvider.MICROSOFT.value == "microsoft"

    def test_is_str_enum(self) -> None:
        """OAuthProvider should be usable as a string."""
        assert str(OAuthProvider.GOOGLE) == "google"
        assert f"{OAuthProvider.GITHUB}" == "github"
