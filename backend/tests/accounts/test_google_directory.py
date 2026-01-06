"""
Tests for Google Directory API client.

Tests token retrieval from Stytch and directory user search.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from stytch.core.response_base import StytchError, StytchErrorDetails

from apps.accounts.google_directory import (
    DirectoryUser,
    get_google_access_token,
    search_directory_users,
)
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


@dataclass
class MockGoogleOAuthResponse:
    """Mock Stytch Google OAuth response."""

    access_token: str | None


class TestGetGoogleAccessToken:
    """Tests for get_google_access_token function."""

    @patch("apps.accounts.google_directory.get_stytch_client")
    def test_returns_token_on_success(self, mock_get_client: MagicMock) -> None:
        """Should return access token when Stytch call succeeds."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.google.return_value = (
            MockGoogleOAuthResponse(access_token="google-access-token-123")
        )
        mock_get_client.return_value = mock_client

        result = get_google_access_token("org-123", "member-456")

        assert result == "google-access-token-123"
        mock_client.organizations.members.oauth_providers.google.assert_called_once_with(
            organization_id="org-123",
            member_id="member-456",
        )

    @patch("apps.accounts.google_directory.get_stytch_client")
    def test_returns_none_on_stytch_error(self, mock_get_client: MagicMock) -> None:
        """Should return None when Stytch returns an error."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.google.side_effect = StytchError(
            StytchErrorDetails(
                status_code=404,
                request_id="req-123",
                error_type="member_not_found",
                error_message="No Google OAuth tokens for this member",
            )
        )
        mock_get_client.return_value = mock_client

        result = get_google_access_token("org-123", "member-789")

        assert result is None

    @patch("apps.accounts.google_directory.get_stytch_client")
    def test_returns_none_when_token_is_none(self, mock_get_client: MagicMock) -> None:
        """Should return None when Stytch returns no access token."""
        mock_client = MagicMock()
        mock_client.organizations.members.oauth_providers.google.return_value = (
            MockGoogleOAuthResponse(access_token=None)
        )
        mock_get_client.return_value = mock_client

        result = get_google_access_token("org-123", "member-456")

        assert result is None


@pytest.mark.django_db
class TestSearchDirectoryUsers:
    """Tests for search_directory_users function."""

    def setup_method(self) -> None:
        """Create test user and member."""
        self.org = OrganizationFactory()
        self.user = UserFactory(email="admin@example.com")
        self.member = MemberFactory(
            user=self.user,
            organization=self.org,
            role="admin",
        )

    @patch("apps.accounts.google_directory.get_google_access_token")
    def test_returns_empty_list_when_no_oauth_token(self, mock_get_token: MagicMock) -> None:
        """Should return empty list when user has no Google OAuth token."""
        mock_get_token.return_value = None

        result = search_directory_users(self.user, self.member, "test query")

        assert result == []

    @patch("apps.accounts.google_directory.httpx.get")
    @patch("apps.accounts.google_directory.get_google_access_token")
    def test_returns_users_on_success(
        self, mock_get_token: MagicMock, mock_httpx_get: MagicMock
    ) -> None:
        """Should return list of DirectoryUser on successful API call."""
        mock_get_token.return_value = "google-access-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "users": [
                {
                    "primaryEmail": "user1@example.com",
                    "name": {"fullName": "User One"},
                    "thumbnailPhotoUrl": "https://photo.example.com/1",
                },
                {
                    "primaryEmail": "user2@example.com",
                    "name": {"fullName": "User Two"},
                    "thumbnailPhotoUrl": "",
                },
            ]
        }
        mock_httpx_get.return_value = mock_response

        result = search_directory_users(self.user, self.member, "user")

        assert len(result) == 2
        assert isinstance(result[0], DirectoryUser)
        assert result[0].email == "user1@example.com"
        assert result[0].name == "User One"
        assert result[0].avatar_url == "https://photo.example.com/1"
        assert result[1].email == "user2@example.com"
        assert result[1].name == "User Two"

    @patch("apps.accounts.google_directory.httpx.get")
    @patch("apps.accounts.google_directory.get_google_access_token")
    def test_returns_empty_list_on_403_forbidden(
        self, mock_get_token: MagicMock, mock_httpx_get: MagicMock
    ) -> None:
        """Should return empty list when user lacks Directory API access."""
        mock_get_token.return_value = "google-access-token"
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_httpx_get.return_value = mock_response

        result = search_directory_users(self.user, self.member, "query")

        assert result == []

    @patch("apps.accounts.google_directory.httpx.get")
    @patch("apps.accounts.google_directory.get_google_access_token")
    def test_returns_empty_list_on_http_error(
        self, mock_get_token: MagicMock, mock_httpx_get: MagicMock
    ) -> None:
        """Should return empty list on HTTP errors."""
        import httpx

        mock_get_token.return_value = "google-access-token"
        mock_httpx_get.side_effect = httpx.ConnectError("Connection failed")

        result = search_directory_users(self.user, self.member, "query")

        assert result == []

    def test_returns_empty_list_when_user_email_invalid(self) -> None:
        """Should return empty list when user email has no domain."""
        user_no_domain = UserFactory(email="invalid-email")
        member_no_domain = MemberFactory(user=user_no_domain, organization=self.org, role="member")

        with patch("apps.accounts.google_directory.get_google_access_token") as mock_get_token:
            mock_get_token.return_value = "google-access-token"
            result = search_directory_users(user_no_domain, member_no_domain, "query")

        assert result == []

    @patch("apps.accounts.google_directory.httpx.get")
    @patch("apps.accounts.google_directory.get_google_access_token")
    def test_uses_correct_api_params(
        self, mock_get_token: MagicMock, mock_httpx_get: MagicMock
    ) -> None:
        """Should call Google API with correct parameters."""
        mock_get_token.return_value = "google-access-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"users": []}
        mock_httpx_get.return_value = mock_response

        search_directory_users(self.user, self.member, "search query", limit=5)

        mock_httpx_get.assert_called_once()
        call_args = mock_httpx_get.call_args
        assert call_args[1]["params"]["domain"] == "example.com"
        assert call_args[1]["params"]["query"] == "search query"
        assert call_args[1]["params"]["maxResults"] == 5
        assert call_args[1]["headers"]["Authorization"] == "Bearer google-access-token"
