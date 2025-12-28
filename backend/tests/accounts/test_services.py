"""
Tests for accounts services.
"""

from dataclasses import dataclass

import pytest

from apps.accounts.models import Member, User
from apps.accounts.services import (
    get_or_create_member_from_stytch,
    get_or_create_organization_from_stytch,
    get_or_create_user_from_stytch,
    sync_session_to_local,
)
from apps.organizations.models import Organization

from .factories import MemberFactory, OrganizationFactory, UserFactory


@pytest.mark.django_db
class TestGetOrCreateUserFromStytch:
    """Tests for get_or_create_user_from_stytch service."""

    def test_creates_new_user(self) -> None:
        """Should create a new user when none exists."""
        user = get_or_create_user_from_stytch(
            stytch_user_id="user-new-123",
            email="new@example.com",
            name="New User",
        )

        assert user.stytch_user_id == "user-new-123"
        assert user.email == "new@example.com"
        assert user.name == "New User"
        assert User.objects.count() == 1

    def test_updates_existing_user(self) -> None:
        """Should update an existing user when one exists."""
        existing = UserFactory(
            stytch_user_id="user-existing-123",
            email="old@example.com",
            name="Old Name",
        )

        user = get_or_create_user_from_stytch(
            stytch_user_id="user-existing-123",
            email="updated@example.com",
            name="Updated Name",
        )

        assert user.id == existing.id
        assert user.email == "updated@example.com"
        assert user.name == "Updated Name"
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
        existing = OrganizationFactory(
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
        user = UserFactory()
        org = OrganizationFactory()

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
        existing = MemberFactory(
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
            roles: list[str]  # type: ignore[type-arg]

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

        # Check user
        assert user.stytch_user_id == "user-abc-123"  # member- replaced with user-
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
            roles: list[str]  # type: ignore[type-arg]

        @dataclass
        class MockStytchOrg:
            organization_id: str
            organization_name: str
            organization_slug: str

        stytch_member = MockStytchMember(
            member_id="member-admin-123",
            email_address="admin@example.com",
            name="Admin User",
            roles=["stytch_admin", "viewer"],
        )
        stytch_org = MockStytchOrg(
            organization_id="org-admin-789",
            organization_name="Admin Corp",
            organization_slug="admin-corp",
        )

        user, member, org = sync_session_to_local(stytch_member, stytch_org)

        assert member.role == "admin"
        assert member.is_admin is True
