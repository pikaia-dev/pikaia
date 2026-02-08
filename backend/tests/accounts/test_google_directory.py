"""
Tests for Google Directory API client.

Tests token retrieval from Stytch and directory user search.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from apps.accounts.google_directory import (
    DirectoryUser,
    get_google_access_token,
    search_directory_users,
)
from apps.accounts.oauth_providers import OAuthProvider
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


class TestGetGoogleAccessToken:
    """Tests for get_google_access_token - verifies it delegates to get_oauth_token."""

    @patch("apps.accounts.google_directory.get_oauth_token")
    def test_delegates_to_get_oauth_token(self, mock_get_oauth_token: MagicMock) -> None:
        """Should delegate to get_oauth_token with GOOGLE provider."""
        mock_get_oauth_token.return_value = "google-access-token-123"

        result = get_google_access_token("org-123", "member-456")

        assert result == "google-access-token-123"
        mock_get_oauth_token.assert_called_once_with(OAuthProvider.GOOGLE, "org-123", "member-456")

    @patch("apps.accounts.google_directory.get_oauth_token")
    def test_returns_none_when_no_token(self, mock_get_oauth_token: MagicMock) -> None:
        """Should return None when get_oauth_token returns None."""
        mock_get_oauth_token.return_value = None

        result = get_google_access_token("org-123", "member-456")

        assert result is None


@pytest.mark.django_db
class TestSearchDirectoryUsers:
    """Tests for search_directory_users function."""

    def setup_method(self) -> None:
        """Create test user and member."""
        self.org = OrganizationFactory.create()
        self.user = UserFactory.create(email="admin@example.com")
        self.member = MemberFactory.create(
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
        mock_get_token.return_value = "google-access-token"
        mock_httpx_get.side_effect = httpx.ConnectError("Connection failed")

        result = search_directory_users(self.user, self.member, "query")

        assert result == []

    def test_returns_empty_list_when_user_email_invalid(self) -> None:
        """Should return empty list when user email has no domain."""
        user_no_domain = UserFactory.create(email="invalid-email")
        member_with_invalid_email = MemberFactory.create(
            user=user_no_domain, organization=self.org, role="member"
        )

        with patch("apps.accounts.google_directory.get_google_access_token") as mock_get_token:
            mock_get_token.return_value = "google-access-token"
            result = search_directory_users(user_no_domain, member_with_invalid_email, "query")

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
