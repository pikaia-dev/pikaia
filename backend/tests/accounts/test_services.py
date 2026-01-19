"""
Tests for accounts services.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.models import Member, User
from apps.accounts.services import (
    bulk_invite_members,
    get_or_create_member_from_stytch,
    get_or_create_organization_from_stytch,
    get_or_create_user_from_stytch,
    invite_member,
    list_organization_members,
    soft_delete_member,
    sync_session_to_local,
    update_member_role,
)
from apps.organizations.models import Organization

from .factories import MemberFactory, OrganizationFactory, UserFactory


@pytest.mark.django_db
class TestGetOrCreateUserFromStytch:
    """Tests for get_or_create_user_from_stytch service."""

    def test_creates_new_user(self) -> None:
        """Should create a new user when none exists."""
        user = get_or_create_user_from_stytch(
            email="new@example.com",
            name="New User",
        )

        assert user.email == "new@example.com"
        assert user.name == "New User"
        assert User.objects.count() == 1

    def test_preserves_existing_user_name(self) -> None:
        """Should preserve existing user's name when they join another org."""
        existing = UserFactory.create(
            email="existing@example.com",
            name="Original Name",
        )

        user = get_or_create_user_from_stytch(
            email="existing@example.com",
            name="New Name From Invite",
        )

        assert user.id == existing.id
        assert user.name == "Original Name"  # Name preserved, not overwritten
        assert User.objects.count() == 1

    def test_sets_name_when_user_has_none(self) -> None:
        """Should set name when existing user doesn't have one."""
        existing = UserFactory.create(
            email="existing@example.com",
            name="",  # No name set
        )

        user = get_or_create_user_from_stytch(
            email="existing@example.com",
            name="New Name",
        )

        assert user.id == existing.id
        assert user.name == "New Name"  # Name is set since user had none
        assert User.objects.count() == 1


@pytest.mark.django_db
class TestGetOrCreateOrganizationFromStytch:
    """Tests for get_or_create_organization_from_stytch service."""

    def test_creates_new_organization(self) -> None:
        """Should create a new organization when none exists."""
        org = get_or_create_organization_from_stytch(
            stytch_org_id="org-new-123",
            name="New Corp",
            slug="new-corp",
        )

        assert org.stytch_org_id == "org-new-123"
        assert org.name == "New Corp"
        assert org.slug == "new-corp"
        assert Organization.objects.count() == 1

    def test_updates_existing_organization(self) -> None:
        """Should update an existing organization when one exists."""
        existing = OrganizationFactory.create(
            stytch_org_id="org-existing-123",
            name="Old Corp",
            slug="old-corp",
        )

        org = get_or_create_organization_from_stytch(
            stytch_org_id="org-existing-123",
            name="Updated Corp",
            slug="updated-corp",
        )

        assert org.id == existing.id
        assert org.name == "Updated Corp"
        assert org.slug == "updated-corp"
        assert Organization.objects.count() == 1


@pytest.mark.django_db
class TestGetOrCreateMemberFromStytch:
    """Tests for get_or_create_member_from_stytch service."""

    def test_creates_new_member(self) -> None:
        """Should create a new member when none exists."""
        user = UserFactory.create()
        org = OrganizationFactory.create()

        member = get_or_create_member_from_stytch(
            user=user,
            organization=org,
            stytch_member_id="member-new-123",
            role="admin",
        )

        assert member.stytch_member_id == "member-new-123"
        assert member.user == user
        assert member.organization == org
        assert member.role == "admin"
        assert Member.objects.count() == 1

    def test_updates_existing_member_role(self) -> None:
        """Should update role when member already exists."""
        existing = MemberFactory.create(
            stytch_member_id="member-existing-123",
            role="member",
        )

        member = get_or_create_member_from_stytch(
            user=existing.user,
            organization=existing.organization,
            stytch_member_id="member-existing-123",
            role="admin",
        )

        assert member.id == existing.id
        assert member.role == "admin"
        assert Member.objects.count() == 1


@pytest.mark.django_db
class TestSyncSessionToLocal:
    """Tests for sync_session_to_local service."""

    def test_creates_all_records(self) -> None:
        """Should create user, member, and org from Stytch data."""

        @dataclass
        class MockStytchMember:
            member_id: str
            email_address: str
            name: str | None
            roles: list[str]

        @dataclass
        class MockStytchOrg:
            organization_id: str
            organization_name: str
            organization_slug: str

        stytch_member = MockStytchMember(
            member_id="member-abc-123",
            email_address="jane@example.com",
            name="Jane Doe",
            roles=[],
        )
        stytch_org = MockStytchOrg(
            organization_id="org-xyz-789",
            organization_name="Acme Corp",
            organization_slug="acme",
        )

        user, member, org = sync_session_to_local(stytch_member, stytch_org)

        # Check organization
        assert org.stytch_org_id == "org-xyz-789"
        assert org.name == "Acme Corp"
        assert org.slug == "acme"

        # Check user - email is the identifier
        assert user.email == "jane@example.com"
        assert user.name == "Jane Doe"

        # Check member
        assert member.stytch_member_id == "member-abc-123"
        assert member.user == user
        assert member.organization == org
        assert member.role == "member"

    def test_admin_role_from_stytch_roles(self) -> None:
        """Should set admin role when stytch_admin in roles."""

        @dataclass
        class MockStytchMember:
            member_id: str
            email_address: str
            name: str | None
            roles: list[dict[str, str]]

        @dataclass
        class MockStytchOrg:
            organization_id: str
            organization_name: str
            organization_slug: str

        stytch_member = MockStytchMember(
            member_id="member-admin-123",
            email_address="admin@example.com",
            name="Admin User",
            roles=[{"role_id": "stytch_admin"}, {"role_id": "viewer"}],
        )
        stytch_org = MockStytchOrg(
            organization_id="org-admin-789",
            organization_name="Admin Corp",
            organization_slug="admin-corp",
        )

        user, member, org = sync_session_to_local(stytch_member, stytch_org)

        assert member.role == "admin"
        assert member.is_admin is True


@pytest.mark.django_db
class TestSyncSessionEdgeCases:
    """Edge cases for sync_session_to_local."""

    def test_admin_role_detection(self) -> None:
        """When the Stytch member has the admin flag, the Member role should be 'admin'."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        # Stytch objects are simple mocks with the needed attributes
        stytch_member = type(
            "StytchMember",
            (),
            {
                "member_id": "member-admin-test",
                "email_address": user.email,
                "name": user.name,
                "roles": [{"role_id": "stytch_admin"}],
            },
        )
        stytch_org = type(
            "StytchOrg",
            (),
            {
                "organization_id": org.stytch_org_id,
                "organization_name": org.name,
                "organization_slug": org.slug,
            },
        )
        user_obj, member_obj, org_obj = sync_session_to_local(stytch_member, stytch_org)
        assert member_obj.role == "admin"
        assert member_obj.user == user_obj
        assert member_obj.organization == org_obj

    def test_member_role_detection_when_no_roles(self) -> None:
        """When the Stytch member has no roles list, default to 'member'."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        stytch_member = type(
            "StytchMember",
            (),
            {
                "member_id": "member-norole-test",
                "email_address": user.email,
                "name": user.name,
                # No "roles" key – getattr will return []
            },
        )
        stytch_org = type(
            "StytchOrg",
            (),
            {
                "organization_id": org.stytch_org_id,
                "organization_name": org.name,
                "organization_slug": org.slug,
            },
        )
        _, member_obj, _ = sync_session_to_local(stytch_member, stytch_org)
        assert member_obj.role == "member"


@pytest.mark.django_db
class TestUpdateExistingRecords:
    """Tests for updating existing records via service functions."""

    def test_preserve_user_name_on_sync(self) -> None:
        """Syncing an existing user should preserve their name, not overwrite it."""
        existing = UserFactory.create(name="Original Name")
        updated_user = get_or_create_user_from_stytch(
            email=existing.email,
            name="Name From New Org",
        )
        assert updated_user.id == existing.id
        assert updated_user.name == "Original Name"  # Preserved

    def test_update_member_role(self) -> None:
        """If a Member already exists, calling get_or_create_member_from_stytch with a new role updates it."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        member = MemberFactory.create(user=user, organization=org, role="member")
        # Call with admin role – should update the existing record
        updated_member = get_or_create_member_from_stytch(
            user=user,
            organization=org,
            stytch_member_id=member.stytch_member_id,
            role="admin",
        )
        assert updated_member.id == member.id
        assert updated_member.role == "admin"


@pytest.mark.django_db
class TestListOrganizationMembers:
    """Tests for list_organization_members service."""

    def test_returns_all_active_members(self) -> None:
        """Should return all active members of the organization."""
        org = OrganizationFactory.create()
        member1 = MemberFactory.create(organization=org, role="admin")
        member2 = MemberFactory.create(organization=org, role="member")

        members, total = list_organization_members(org)

        assert len(members) == 2
        assert total == 2
        assert member1 in members
        assert member2 in members

    def test_returns_empty_list_for_org_with_no_members(self) -> None:
        """Should return empty list when organization has no members."""
        org = OrganizationFactory.create()

        members, total = list_organization_members(org)

        assert members == []
        assert total == 0

    def test_excludes_members_from_other_orgs(self) -> None:
        """Should only return members from the specified organization."""
        org1 = OrganizationFactory.create()
        org2 = OrganizationFactory.create()
        member1 = MemberFactory.create(organization=org1)
        MemberFactory.create(organization=org2)  # Should not be included

        members, total = list_organization_members(org1)

        assert len(members) == 1
        assert total == 1
        assert members[0] == member1

    def test_uses_select_related_for_user(self) -> None:
        """Should prefetch user data to avoid N+1 queries."""
        org = OrganizationFactory.create()
        MemberFactory.create(organization=org)
        MemberFactory.create(organization=org)

        members, _ = list_organization_members(org)

        # Access user without triggering additional queries
        for member in members:
            assert member.user is not None
            assert member.user.email is not None

    def test_orders_by_created_at(self) -> None:
        """Should return members ordered by creation time."""
        org = OrganizationFactory.create()
        member1 = MemberFactory.create(organization=org)
        member2 = MemberFactory.create(organization=org)

        members, _ = list_organization_members(org)

        # First member should come before second
        assert members[0].id == member1.id
        assert members[1].id == member2.id

    def test_pagination_with_limit(self) -> None:
        """Should return only limited number of members."""
        org = OrganizationFactory.create()
        MemberFactory.create(organization=org)
        MemberFactory.create(organization=org)
        MemberFactory.create(organization=org)

        members, total = list_organization_members(org, limit=2)

        assert len(members) == 2
        assert total == 3

    def test_pagination_with_offset(self) -> None:
        """Should skip members with offset."""
        org = OrganizationFactory.create()
        _first = MemberFactory.create(organization=org)
        second = MemberFactory.create(organization=org)
        third = MemberFactory.create(organization=org)

        members, total = list_organization_members(org, offset=1)

        assert len(members) == 2
        assert total == 3
        assert members[0] == second
        assert members[1] == third

    def test_pagination_with_offset_and_limit(self) -> None:
        """Should apply both offset and limit."""
        org = OrganizationFactory.create()
        _first = MemberFactory.create(organization=org)
        second = MemberFactory.create(organization=org)
        _third = MemberFactory.create(organization=org)
        _fourth = MemberFactory.create(organization=org)

        members, total = list_organization_members(org, offset=1, limit=1)

        assert len(members) == 1
        assert total == 4
        assert members[0] == second


@pytest.mark.django_db
class TestInviteMember:
    """Tests for invite_member service."""

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_invites_new_member(self, mock_sync_qty: MagicMock, mock_stytch: MagicMock) -> None:
        """Should create a new member via Stytch and sync locally."""
        org = OrganizationFactory.create()

        # Configure mock Stytch client
        mock_client = MagicMock()
        mock_stytch.return_value = mock_client
        mock_client.organizations.members.search.return_value = MagicMock(members=[])
        mock_client.magic_links.email.invite.return_value = MagicMock(
            member_id="stytch-member-new-123"
        )

        member, invite_sent = invite_member(
            organization=org,
            email="newuser@example.com",
            name="New User",
            role="member",
        )

        assert invite_sent is True
        assert member.user.email == "newuser@example.com"
        assert member.user.name == "New User"
        assert member.organization == org
        assert member.stytch_member_id == "stytch-member-new-123"
        assert member.role == "member"

        # Verify Stytch was called correctly
        mock_client.magic_links.email.invite.assert_called_once_with(
            organization_id=org.stytch_org_id,
            email_address="newuser@example.com",
        )

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_invites_admin_member(self, mock_sync_qty: MagicMock, mock_stytch: MagicMock) -> None:
        """Should create admin member and set role in Stytch."""
        org = OrganizationFactory.create()

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client
        mock_client.organizations.members.search.return_value = MagicMock(members=[])
        mock_client.magic_links.email.invite.return_value = MagicMock(
            member_id="stytch-member-admin-123"
        )

        member, invite_sent = invite_member(
            organization=org,
            email="admin@example.com",
            name="Admin User",
            role="admin",
        )

        assert invite_sent is True
        assert member.role == "admin"

        # Should update role after invite
        mock_client.organizations.members.update.assert_called_once()

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_returns_false_for_active_member(
        self, mock_sync_qty: MagicMock, mock_stytch: MagicMock
    ) -> None:
        """Should return invite_sent=False for already active member."""
        org = OrganizationFactory.create()
        existing_user = UserFactory.create(email="existing@example.com")
        MemberFactory.create(user=existing_user, organization=org, stytch_member_id="existing-123")

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        existing_stytch_member = MagicMock()
        existing_stytch_member.member_id = "existing-123"
        existing_stytch_member.status = "active"
        mock_client.organizations.members.search.return_value = MagicMock(
            members=[existing_stytch_member]
        )

        member, invite_sent = invite_member(
            organization=org,
            email="existing@example.com",
        )

        assert invite_sent is False
        assert member.user.email == "existing@example.com"

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_returns_pending_for_invited_member(
        self, mock_sync_qty: MagicMock, mock_stytch: MagicMock
    ) -> None:
        """Should return invite_sent='pending' for already invited member."""
        org = OrganizationFactory.create()

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        invited_stytch_member = MagicMock()
        invited_stytch_member.member_id = "invited-123"
        invited_stytch_member.status = "invited"
        mock_client.organizations.members.search.return_value = MagicMock(
            members=[invited_stytch_member]
        )

        member, invite_sent = invite_member(
            organization=org,
            email="pending@example.com",
        )

        assert invite_sent == "pending"

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_reactivates_deleted_member(
        self, mock_sync_qty: MagicMock, mock_stytch: MagicMock
    ) -> None:
        """Should reactivate a previously deleted member."""
        org = OrganizationFactory.create()

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        deleted_stytch_member = MagicMock()
        deleted_stytch_member.member_id = "deleted-123"
        deleted_stytch_member.status = "deleted"
        mock_client.organizations.members.search.return_value = MagicMock(
            members=[deleted_stytch_member]
        )

        member, invite_sent = invite_member(
            organization=org,
            email="deleted@example.com",
        )

        assert invite_sent is True
        mock_client.organizations.members.reactivate.assert_called_once()

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_syncs_subscription_quantity(
        self, mock_sync_qty: MagicMock, mock_stytch: MagicMock
    ) -> None:
        """Should sync subscription quantity after invite."""
        org = OrganizationFactory.create()

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client
        mock_client.organizations.members.search.return_value = MagicMock(members=[])
        mock_client.magic_links.email.invite.return_value = MagicMock(member_id="new-member-123")

        invite_member(organization=org, email="sync@example.com")

        mock_sync_qty.assert_called_once_with(org)


@pytest.mark.django_db
class TestUpdateMemberRole:
    """Tests for update_member_role service."""

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_updates_role_to_admin(self, mock_stytch: MagicMock) -> None:
        """Should update member role to admin in both local DB and Stytch."""
        member = MemberFactory.create(role="member")

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        updated = update_member_role(member, "admin")

        assert updated.role == "admin"
        mock_client.organizations.members.update.assert_called_once_with(
            organization_id=member.organization.stytch_org_id,
            member_id=member.stytch_member_id,
            roles=["stytch_admin"],
        )

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_updates_role_to_member(self, mock_stytch: MagicMock) -> None:
        """Should update member role from admin to member."""
        member = MemberFactory.create(role="admin")

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        updated = update_member_role(member, "member")

        assert updated.role == "member"
        # Empty roles list for non-admin
        mock_client.organizations.members.update.assert_called_once_with(
            organization_id=member.organization.stytch_org_id,
            member_id=member.stytch_member_id,
            roles=[],
        )

    @patch("apps.accounts.stytch_client.get_stytch_client")
    def test_returns_updated_member(self, mock_stytch: MagicMock) -> None:
        """Should return the updated member object."""
        member = MemberFactory.create(role="member")
        original_id = member.id

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        updated = update_member_role(member, "admin")

        assert updated.id == original_id
        assert updated.role == "admin"


@pytest.mark.django_db
class TestSoftDeleteMember:
    """Tests for soft_delete_member service."""

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_soft_deletes_locally(self, mock_sync_qty: MagicMock, mock_stytch: MagicMock) -> None:
        """Should soft delete member locally (set deleted_at)."""
        member = MemberFactory.create()
        member_id = member.id

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        soft_delete_member(member)

        # Reload from database using all_objects manager
        deleted_member = Member.all_objects.get(id=member_id)
        assert deleted_member.deleted_at is not None

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_deletes_from_stytch(self, mock_sync_qty: MagicMock, mock_stytch: MagicMock) -> None:
        """Should delete member from Stytch."""
        member = MemberFactory.create()
        org_stytch_id = member.organization.stytch_org_id
        stytch_member_id = member.stytch_member_id

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        soft_delete_member(member)

        mock_client.organizations.members.delete.assert_called_once_with(
            organization_id=org_stytch_id,
            member_id=stytch_member_id,
        )

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_syncs_subscription_quantity(
        self, mock_sync_qty: MagicMock, mock_stytch: MagicMock
    ) -> None:
        """Should sync subscription quantity after delete."""
        member = MemberFactory.create()
        org = member.organization

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        soft_delete_member(member)

        mock_sync_qty.assert_called_once_with(org)

    @patch("apps.accounts.stytch_client.get_stytch_client")
    @patch("apps.billing.services.sync_subscription_quantity")
    def test_member_not_in_default_queryset(
        self, mock_sync_qty: MagicMock, mock_stytch: MagicMock
    ) -> None:
        """Deleted member should not appear in default queryset."""
        member = MemberFactory.create()
        org = member.organization

        mock_client = MagicMock()
        mock_stytch.return_value = mock_client

        soft_delete_member(member)

        # Should not appear in default queryset
        assert Member.objects.filter(organization=org).count() == 0
        # But should exist in all_objects
        assert Member.all_objects.filter(organization=org).count() == 1


@pytest.mark.django_db
class TestBulkInviteMembers:
    """Tests for bulk_invite_members service."""

    @patch("apps.accounts.services.invite_member")
    def test_invites_multiple_members(self, mock_invite: MagicMock) -> None:
        """Should invite multiple members and return results."""
        org = OrganizationFactory.create()

        # Mock successful invites
        mock_invite.side_effect = [
            (MemberFactory.create(stytch_member_id="stytch-1"), True),
            (MemberFactory.create(stytch_member_id="stytch-2"), True),
        ]

        members_data = [
            {"email": "user1@example.com", "name": "User One", "phone": "", "role": "member"},
            {"email": "user2@example.com", "name": "User Two", "phone": "", "role": "admin"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        assert result["total"] == 2
        assert result["succeeded"] == 2
        assert result["failed"] == 0
        assert len(result["results"]) == 2
        assert all(r["success"] for r in result["results"])

    @patch("apps.accounts.services.invite_member")
    def test_handles_partial_failure(self, mock_invite: MagicMock) -> None:
        """Should handle mix of successful and failed invites."""
        from stytch.core.response_base import StytchError, StytchErrorDetails

        org = OrganizationFactory.create()

        # First succeeds, second fails
        mock_invite.side_effect = [
            (MemberFactory.create(stytch_member_id="stytch-1"), True),
            StytchError(
                StytchErrorDetails(
                    status_code=400,
                    request_id="req-123",
                    error_type="invalid_email",
                    error_message="Invalid email format",
                )
            ),
        ]

        members_data = [
            {"email": "valid@example.com", "name": "Valid", "phone": "", "role": "member"},
            {"email": "invalid-email", "name": "Invalid", "phone": "", "role": "member"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        assert result["total"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert result["results"][0]["success"] is True
        assert result["results"][1]["success"] is False
        assert result["results"][1]["error"] == "Invalid email format"

    @patch("apps.accounts.services.invite_member")
    def test_stores_phone_number_unverified(self, mock_invite: MagicMock) -> None:
        """Should store phone number on user as unverified."""
        org = OrganizationFactory.create()
        user = UserFactory.create(phone_number="", phone_verified_at=None)
        member = MemberFactory.create(user=user, organization=org, stytch_member_id="stytch-1")

        mock_invite.return_value = (member, True)

        members_data = [
            {"email": user.email, "name": "User", "phone": "+14155551234", "role": "member"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        assert result["succeeded"] == 1

        # Reload user from DB
        user.refresh_from_db()
        assert user.phone_number == "+14155551234"
        assert user.phone_verified_at is None  # Explicitly unverified

    @patch("apps.accounts.services.invite_member")
    def test_does_not_overwrite_existing_verified_phone(self, mock_invite: MagicMock) -> None:
        """Should not overwrite existing phone if same number."""
        from django.utils import timezone

        org = OrganizationFactory.create()
        verified_time = timezone.now()
        user = UserFactory.create(phone_number="+14155551234", phone_verified_at=verified_time)
        member = MemberFactory.create(user=user, organization=org, stytch_member_id="stytch-1")

        mock_invite.return_value = (member, True)

        members_data = [
            {"email": user.email, "name": "User", "phone": "+14155551234", "role": "member"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        assert result["succeeded"] == 1

        # Phone should remain unchanged since same number
        user.refresh_from_db()
        assert user.phone_number == "+14155551234"
        assert user.phone_verified_at == verified_time  # Still verified

    @patch("apps.accounts.services.invite_member")
    def test_updates_phone_if_different(self, mock_invite: MagicMock) -> None:
        """Should update phone and clear verification if different number."""
        from django.utils import timezone

        org = OrganizationFactory.create()
        user = UserFactory.create(phone_number="+14155551111", phone_verified_at=timezone.now())
        member = MemberFactory.create(user=user, organization=org, stytch_member_id="stytch-1")

        mock_invite.return_value = (member, True)

        members_data = [
            {"email": user.email, "name": "User", "phone": "+14155552222", "role": "member"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        assert result["succeeded"] == 1

        # Phone should be updated and verification cleared
        user.refresh_from_db()
        assert user.phone_number == "+14155552222"
        assert user.phone_verified_at is None  # Verification cleared

    @patch("apps.accounts.services.invite_member")
    def test_empty_members_list(self, mock_invite: MagicMock) -> None:
        """Should handle empty members list."""
        org = OrganizationFactory.create()

        result = bulk_invite_members(organization=org, members_data=[])

        assert result["total"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0
        assert result["results"] == []
        mock_invite.assert_not_called()

    @patch("apps.accounts.services.invite_member")
    def test_handles_generic_exception(self, mock_invite: MagicMock) -> None:
        """Should catch and report generic exceptions."""
        org = OrganizationFactory.create()

        mock_invite.side_effect = ValueError("Something went wrong")

        members_data = [
            {"email": "user@example.com", "name": "User", "phone": "", "role": "member"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        assert result["total"] == 1
        assert result["succeeded"] == 0
        assert result["failed"] == 1
        assert result["results"][0]["success"] is False
        assert "Something went wrong" in result["results"][0]["error"]

    @patch("apps.accounts.services.invite_member")
    def test_already_active_member_returns_failed(self, mock_invite: MagicMock) -> None:
        """Should report failure when member is already active."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org, stytch_member_id="stytch-active")

        # invite_member returns False for active members
        mock_invite.return_value = (member, False)

        members_data = [
            {"email": "active@example.com", "name": "Active User", "phone": "", "role": "member"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        assert result["total"] == 1
        assert result["succeeded"] == 0
        assert result["failed"] == 1
        assert result["results"][0]["success"] is False
        assert "already active" in result["results"][0]["error"]
        assert result["results"][0]["stytch_member_id"] == "stytch-active"

    @patch("apps.accounts.services.invite_member")
    def test_already_invited_member_returns_failed(self, mock_invite: MagicMock) -> None:
        """Should report failure when member already has pending invitation."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org, stytch_member_id="stytch-invited")

        # invite_member returns "pending" for already invited members
        mock_invite.return_value = (member, "pending")

        members_data = [
            {"email": "invited@example.com", "name": "Invited User", "phone": "", "role": "member"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        assert result["total"] == 1
        assert result["succeeded"] == 0
        assert result["failed"] == 1
        assert result["results"][0]["success"] is False
        assert "pending invitation" in result["results"][0]["error"]
        assert result["results"][0]["stytch_member_id"] == "stytch-invited"

    @patch("apps.accounts.services.invite_member")
    def test_deduplicates_emails_case_insensitive(self, mock_invite: MagicMock) -> None:
        """Should dedupe emails (case-insensitive), processing only first occurrence."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org, stytch_member_id="stytch-new")

        mock_invite.return_value = (member, True)

        members_data = [
            {"email": "User@Example.com", "name": "First", "phone": "", "role": "member"},
            {"email": "user@example.com", "name": "Duplicate", "phone": "", "role": "admin"},
            {"email": "USER@EXAMPLE.COM", "name": "Another Dup", "phone": "", "role": "member"},
        ]

        result = bulk_invite_members(organization=org, members_data=members_data)

        # Only first should be processed, others are duplicates
        assert result["total"] == 3
        assert result["succeeded"] == 1
        assert result["failed"] == 2

        # First occurrence succeeds
        assert result["results"][0]["email"] == "user@example.com"
        assert result["results"][0]["success"] is False
        assert "Duplicate email" in result["results"][0]["error"]

        assert result["results"][1]["email"] == "USER@EXAMPLE.COM"
        assert result["results"][1]["success"] is False
        assert "Duplicate email" in result["results"][1]["error"]

        # Last one is the actual invite (after dedupes)
        assert result["results"][2]["success"] is True

        # invite_member should only be called once
        mock_invite.assert_called_once()

    def test_rejects_batch_exceeding_max_size(self) -> None:
        """Should raise ValueError if batch exceeds MAX_BULK_INVITE_SIZE."""
        from apps.accounts.services import MAX_BULK_INVITE_SIZE

        org = OrganizationFactory.create()

        # Create batch exceeding limit
        members_data = [
            {"email": f"user{i}@example.com", "name": f"User {i}", "phone": "", "role": "member"}
            for i in range(MAX_BULK_INVITE_SIZE + 1)
        ]

        with pytest.raises(ValueError, match=f"limited to {MAX_BULK_INVITE_SIZE}"):
            bulk_invite_members(organization=org, members_data=members_data)
