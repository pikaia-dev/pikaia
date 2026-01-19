"""
Tests for accounts models.
"""

import pytest
from django.db import IntegrityError

from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


@pytest.mark.django_db
class TestUserModel:
    """Tests for User model."""

    def test_create_user(self) -> None:
        """Should create a user with required fields."""
        user = UserFactory.create()

        assert user.pk is not None
        assert user.is_active is True
        assert user.is_staff is False

    def test_user_str(self) -> None:
        """String representation should be email."""
        user = UserFactory.create(email="test@example.com")

        assert str(user) == "test@example.com"

    def test_email_unique(self) -> None:
        """Email must be unique."""
        UserFactory.create(email="duplicate@example.com")

        with pytest.raises(IntegrityError):
            UserFactory.create(email="duplicate@example.com")


@pytest.mark.django_db
class TestMemberModel:
    """Tests for Member model."""

    def test_create_member(self) -> None:
        """Should create a member linking user to org."""
        member = MemberFactory.create()

        assert member.pk is not None
        assert member.user is not None
        assert member.organization is not None

    def test_member_str(self) -> None:
        """String representation should be user @ org."""
        user = UserFactory.create(email="jane@example.com")
        org = OrganizationFactory.create(name="Acme Corp")
        member = MemberFactory.create(user=user, organization=org)

        assert str(member) == "jane@example.com @ Acme Corp (member)"

    def test_is_admin_true_for_admin_role(self) -> None:
        """is_admin should be True for admin role."""
        member = MemberFactory.create(role="admin")

        assert member.is_admin is True

    def test_is_admin_false_for_member_role(self) -> None:
        """is_admin should be False for member role."""
        member = MemberFactory.create(role="member")

        assert member.is_admin is False

    def test_unique_user_org_combination(self) -> None:
        """User can only have one membership per org."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        MemberFactory.create(user=user, organization=org)

        with pytest.raises(IntegrityError):
            MemberFactory.create(user=user, organization=org)

    def test_user_can_be_in_multiple_orgs(self) -> None:
        """User can be member of multiple organizations."""
        user = UserFactory.create()
        org1 = OrganizationFactory.create()
        org2 = OrganizationFactory.create()

        m1 = MemberFactory.create(user=user, organization=org1)
        m2 = MemberFactory.create(user=user, organization=org2)

        assert m1.pk is not None
        assert m2.pk is not None
        assert user.memberships.count() == 2

    def test_member_has_organization_deleted_at_index(self) -> None:
        """Member model should have composite index on organization and deleted_at."""
        from apps.accounts.models import Member

        # Check that the model has the expected index
        # This test verifies the index is defined in the model Meta
        indexes = Member._meta.indexes
        index_fields_list = [tuple(index.fields) for index in indexes]

        # Verify the composite index exists
        assert ("organization", "deleted_at") in index_fields_list
