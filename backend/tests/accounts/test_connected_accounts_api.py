"""
Tests for connected accounts API endpoints and service functions.
"""

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.models import ConnectedAccount
from apps.accounts.services import (
    get_connected_accounts_from_stytch,
    sync_connected_accounts_from_member_data,
)
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


@dataclass
class MockOAuthRegistration:
    """Mock Stytch OAuth registration."""

    provider_type: str
    provider_subject: str = ""


@dataclass
class MockStytchMember:
    """Mock Stytch member with oauth_registrations."""

    member_id: str = "member-test-1"
    email_address: str = "test@example.com"
    name: str = "Test User"
    oauth_registrations: list[MockOAuthRegistration] = field(default_factory=list)


@pytest.mark.django_db
class TestSyncConnectedAccountsFromMemberData:
    """Tests for sync_connected_accounts_from_member_data."""

    def setup_method(self) -> None:
        self.org = OrganizationFactory.create()
        self.user = UserFactory.create()
        self.member = MemberFactory.create(user=self.user, organization=self.org)

    def test_creates_connected_accounts_from_registrations(self) -> None:
        """Should create ConnectedAccount records from Stytch registrations."""
        stytch_member = MockStytchMember(
            oauth_registrations=[
                MockOAuthRegistration(provider_type="google", provider_subject="google-sub-123"),
                MockOAuthRegistration(provider_type="github", provider_subject="github-sub-456"),
            ]
        )

        sync_connected_accounts_from_member_data(self.member, stytch_member)

        accounts = ConnectedAccount.objects.filter(member=self.member).order_by("provider")
        assert accounts.count() == 2
        assert accounts[0].provider == "github"
        assert accounts[0].provider_subject == "github-sub-456"
        assert accounts[1].provider == "google"
        assert accounts[1].provider_subject == "google-sub-123"

    def test_updates_existing_accounts(self) -> None:
        """Should update provider_subject for existing accounts."""
        ConnectedAccount.objects.create(
            member=self.member,
            provider="google",
            provider_subject="old-sub",
        )

        stytch_member = MockStytchMember(
            oauth_registrations=[
                MockOAuthRegistration(provider_type="google", provider_subject="new-sub"),
            ]
        )

        sync_connected_accounts_from_member_data(self.member, stytch_member)

        account = ConnectedAccount.objects.get(member=self.member, provider="google")
        assert account.provider_subject == "new-sub"

    def test_removes_stale_accounts(self) -> None:
        """Should remove accounts no longer in Stytch registrations."""
        ConnectedAccount.objects.create(
            member=self.member, provider="google", provider_subject="sub-1"
        )
        ConnectedAccount.objects.create(
            member=self.member, provider="github", provider_subject="sub-2"
        )

        # Only google remains
        stytch_member = MockStytchMember(
            oauth_registrations=[
                MockOAuthRegistration(provider_type="google", provider_subject="sub-1"),
            ]
        )

        sync_connected_accounts_from_member_data(self.member, stytch_member)

        accounts = ConnectedAccount.objects.filter(member=self.member)
        assert accounts.count() == 1
        first = accounts.first()
        assert first is not None
        assert first.provider == "google"

    def test_empty_registrations_deletes_existing(self) -> None:
        """Should delete existing records when Stytch returns an empty list (all disconnected)."""
        ConnectedAccount.objects.create(
            member=self.member, provider="google", provider_subject="sub-1"
        )

        stytch_member = MockStytchMember(oauth_registrations=[])

        sync_connected_accounts_from_member_data(self.member, stytch_member)

        assert ConnectedAccount.objects.filter(member=self.member).count() == 0

    def test_missing_attr_does_not_delete_existing(self) -> None:
        """Should preserve records when oauth_registrations attribute is missing entirely."""
        ConnectedAccount.objects.create(
            member=self.member, provider="google", provider_subject="sub-1"
        )

        stytch_member = MagicMock(spec=[])  # No oauth_registrations attribute

        sync_connected_accounts_from_member_data(self.member, stytch_member)

        assert ConnectedAccount.objects.filter(member=self.member).count() == 1

    def test_handles_missing_oauth_registrations_attr_no_records(self) -> None:
        """Should handle Stytch member without oauth_registrations when no records exist."""
        stytch_member = MagicMock(spec=[])  # No attributes

        sync_connected_accounts_from_member_data(self.member, stytch_member)

        assert ConnectedAccount.objects.filter(member=self.member).count() == 0

    def test_skips_registrations_without_provider_type(self) -> None:
        """Should skip registrations with empty provider_type."""
        stytch_member = MockStytchMember(
            oauth_registrations=[
                MockOAuthRegistration(provider_type="", provider_subject="sub-1"),
                MockOAuthRegistration(provider_type="google", provider_subject="sub-2"),
            ]
        )

        sync_connected_accounts_from_member_data(self.member, stytch_member)

        accounts = ConnectedAccount.objects.filter(member=self.member)
        assert accounts.count() == 1
        first = accounts.first()
        assert first is not None
        assert first.provider == "google"


@pytest.mark.django_db
class TestGetConnectedAccountsFromStytch:
    """Tests for get_connected_accounts_from_stytch."""

    def setup_method(self) -> None:
        self.org = OrganizationFactory.create()
        self.user = UserFactory.create()
        self.member = MemberFactory.create(user=self.user, organization=self.org)

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_fetches_and_syncs_from_stytch(self, mock_get_client: MagicMock) -> None:
        """Should fetch member from Stytch and sync connected accounts."""
        # Clear lru_cache so our mock is used
        from apps.accounts.stytch_client import get_stytch_client

        get_stytch_client.cache_clear()

        mock_client = MagicMock()
        mock_member = MockStytchMember(
            oauth_registrations=[
                MockOAuthRegistration(provider_type="google", provider_subject="sub-1"),
            ]
        )
        mock_client.organizations.members.get.return_value = MagicMock(member=mock_member)
        mock_get_client.return_value = mock_client

        accounts = get_connected_accounts_from_stytch(self.member)

        assert len(accounts) == 1
        assert accounts[0].provider == "google"
        mock_client.organizations.members.get.assert_called_once_with(
            organization_id=self.org.stytch_org_id,
            member_id=self.member.stytch_member_id,
        )

        # Clear cache again so mock doesn't leak
        get_stytch_client.cache_clear()

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_returns_existing_accounts_on_stytch_error(self, mock_get_client: MagicMock) -> None:
        """Should return existing local accounts when Stytch call fails."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        from apps.accounts.stytch_client import get_stytch_client

        get_stytch_client.cache_clear()

        ConnectedAccount.objects.create(
            member=self.member, provider="google", provider_subject="sub-1"
        )

        mock_client = MagicMock()
        mock_client.organizations.members.get.side_effect = StytchError(
            StytchErrorDetails(
                status_code=500,
                request_id="req-1",
                error_type="internal_error",
                error_message="Stytch is down",
            )
        )
        mock_get_client.return_value = mock_client

        accounts = get_connected_accounts_from_stytch(self.member)

        assert len(accounts) == 1
        assert accounts[0].provider == "google"

        get_stytch_client.cache_clear()


@pytest.mark.django_db
class TestConnectedAccountsAPIEndpoints:
    """Tests for connected accounts API endpoints (via direct function calls)."""

    def setup_method(self) -> None:
        self.org = OrganizationFactory.create()
        self.user = UserFactory.create()
        self.member = MemberFactory.create(user=self.user, organization=self.org, role="member")

    def test_disconnect_provider_deletes_record(self) -> None:
        """Should delete the ConnectedAccount for the given provider."""
        ConnectedAccount.objects.create(
            member=self.member, provider="google", provider_subject="sub-1"
        )
        ConnectedAccount.objects.create(
            member=self.member, provider="github", provider_subject="sub-2"
        )

        deleted_count, _ = ConnectedAccount.objects.filter(
            member=self.member, provider="google"
        ).delete()

        assert deleted_count == 1
        remaining = ConnectedAccount.objects.filter(member=self.member)
        assert remaining.count() == 1
        first = remaining.first()
        assert first is not None
        assert first.provider == "github"

    def test_disconnect_nonexistent_provider_returns_zero(self) -> None:
        """Should return 0 deleted when provider not found."""
        deleted_count, _ = ConnectedAccount.objects.filter(
            member=self.member, provider="nonexistent"
        ).delete()

        assert deleted_count == 0

    def test_unique_constraint_per_member_provider(self) -> None:
        """Should enforce unique constraint on (member, provider)."""
        from django.db import IntegrityError

        ConnectedAccount.objects.create(
            member=self.member, provider="google", provider_subject="sub-1"
        )

        with pytest.raises(IntegrityError):
            ConnectedAccount.objects.create(
                member=self.member, provider="google", provider_subject="sub-2"
            )

    def test_different_members_can_have_same_provider(self) -> None:
        """Should allow different members to connect the same provider."""
        other_member = MemberFactory.create(organization=self.org)

        ConnectedAccount.objects.create(
            member=self.member, provider="google", provider_subject="sub-1"
        )
        ConnectedAccount.objects.create(
            member=other_member, provider="google", provider_subject="sub-2"
        )

        assert ConnectedAccount.objects.count() == 2
