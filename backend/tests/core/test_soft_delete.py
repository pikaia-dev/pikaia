"""
Tests for soft delete infrastructure.

Tests cover:
- SoftDeleteMixin behavior (soft_delete, restore, hard_delete)
- SoftDeleteManager filtering
- SoftDeleteAllManager access to all records
- SoftDeleteQuerySet bulk operations
- Integration with existing models (Organization, Member)
"""

import pytest

from apps.accounts.models import Member
from apps.organizations.models import Organization
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


@pytest.mark.django_db
class TestSoftDeleteMixin:
    """Tests for SoftDeleteMixin methods and properties."""

    def test_is_deleted_false_by_default(self) -> None:
        """New records should not be marked as deleted."""
        org = OrganizationFactory.create()

        assert org.is_deleted is False
        assert org.deleted_at is None

    def test_soft_delete_sets_timestamp(self) -> None:
        """soft_delete() should set deleted_at to current time."""
        org = OrganizationFactory.create()

        org.soft_delete()

        org.refresh_from_db()
        assert org.is_deleted is True
        assert org.deleted_at is not None

    def test_soft_delete_updates_updated_at(self) -> None:
        """soft_delete() should also update the updated_at field."""
        import time

        org = OrganizationFactory.create()
        original_updated_at = org.updated_at
        time.sleep(0.01)  # Ensure time difference

        org.soft_delete()

        org.refresh_from_db()
        assert org.updated_at > original_updated_at

    def test_soft_delete_skip_timestamp_update(self) -> None:
        """soft_delete(update_timestamp=False) should not update updated_at."""
        org = OrganizationFactory.create()
        original_updated_at = org.updated_at

        org.soft_delete(update_timestamp=False)

        org.refresh_from_db()
        assert org.updated_at == original_updated_at

    def test_restore_clears_deleted_at(self) -> None:
        """restore() should clear the deleted_at timestamp."""
        org = OrganizationFactory.create()
        org.soft_delete()
        assert org.is_deleted is True

        org.restore()

        org.refresh_from_db()
        assert org.is_deleted is False
        assert org.deleted_at is None

    def test_restore_updates_updated_at(self) -> None:
        """restore() should update the updated_at field."""
        import time

        org = OrganizationFactory.create()
        org.soft_delete()
        deleted_updated_at = org.updated_at
        time.sleep(0.01)  # Ensure time difference

        org.restore()

        org.refresh_from_db()
        assert org.updated_at > deleted_updated_at

    def test_hard_delete_removes_from_database(self) -> None:
        """hard_delete() should permanently remove the record."""
        org = OrganizationFactory.create()
        org_id = org.pk

        org.hard_delete()

        assert not Organization.all_objects.filter(pk=org_id).exists()


@pytest.mark.django_db
class TestSoftDeleteManager:
    """Tests for SoftDeleteManager (default objects manager)."""

    def test_excludes_soft_deleted_records(self) -> None:
        """Default manager should not return soft-deleted records."""
        _active_org = OrganizationFactory.create()
        deleted_org = OrganizationFactory.create()
        deleted_org.soft_delete()

        orgs = Organization.objects.all()

        assert orgs.count() == 1
        assert deleted_org not in orgs

    def test_get_raises_for_deleted_record(self) -> None:
        """get() should raise DoesNotExist for soft-deleted records."""
        org = OrganizationFactory.create()
        org_id = org.pk
        org.soft_delete()

        with pytest.raises(Organization.DoesNotExist):
            Organization.objects.get(pk=org_id)

    def test_filter_excludes_deleted(self) -> None:
        """filter() should exclude soft-deleted records."""
        org1 = OrganizationFactory.create(name="Active Org")
        org2 = OrganizationFactory.create(name="Deleted Org")
        org2.soft_delete()

        results = Organization.objects.filter(name__contains="Org")

        assert list(results) == [org1]


@pytest.mark.django_db
class TestSoftDeleteAllManager:
    """Tests for SoftDeleteAllManager (all_objects manager)."""

    def test_includes_all_records(self) -> None:
        """all_objects should return both active and deleted records."""
        active_org = OrganizationFactory.create()
        deleted_org = OrganizationFactory.create()
        deleted_org.soft_delete()

        orgs = Organization.all_objects.all()

        assert orgs.count() == 2
        assert active_org in orgs
        assert deleted_org in orgs

    def test_dead_returns_only_deleted(self) -> None:
        """dead() should return only soft-deleted records."""
        _active_org = OrganizationFactory.create()
        deleted_org = OrganizationFactory.create()
        deleted_org.soft_delete()

        dead_orgs = Organization.all_objects.dead()

        assert dead_orgs.count() == 1
        assert deleted_org in dead_orgs

    def test_get_queryset_alive_method(self) -> None:
        """alive() should filter to non-deleted records."""
        active_org = OrganizationFactory.create()
        deleted_org = OrganizationFactory.create()
        deleted_org.soft_delete()

        alive_orgs = Organization.all_objects.get_queryset().alive()

        assert alive_orgs.count() == 1
        assert active_org in alive_orgs


@pytest.mark.django_db
class TestSoftDeleteQuerySet:
    """Tests for SoftDeleteQuerySet bulk operations."""

    def test_bulk_delete_soft_deletes_all(self) -> None:
        """delete() on queryset should soft delete all matching records."""
        org1 = OrganizationFactory.create(name="Test Org 1")
        org2 = OrganizationFactory.create(name="Test Org 2")
        _other_org = OrganizationFactory.create(name="Other Org")

        count, details = Organization.objects.filter(name__startswith="Test").delete()

        assert count == 2
        assert details["organizations.Organization"] == 2

        org1.refresh_from_db()
        org2.refresh_from_db()
        assert org1.is_deleted is True
        assert org2.is_deleted is True
        assert Organization.all_objects.count() == 3

    def test_bulk_hard_delete_removes_permanently(self) -> None:
        """hard_delete() on queryset should permanently remove records."""
        org1 = OrganizationFactory.create(name="Test Org 1")
        org2 = OrganizationFactory.create(name="Test Org 2")
        _other_org = OrganizationFactory.create(name="Other Org")

        Organization.all_objects.filter(name__startswith="Test").hard_delete()  # type: ignore[attr-defined]

        assert Organization.all_objects.count() == 1
        assert not Organization.all_objects.filter(pk=org1.pk).exists()
        assert not Organization.all_objects.filter(pk=org2.pk).exists()

    def test_dead_filter_on_queryset(self) -> None:
        """dead() on queryset should return deleted records."""
        _active = OrganizationFactory.create()
        deleted = OrganizationFactory.create()
        deleted.soft_delete()

        dead = Organization.all_objects.get_queryset().dead()

        assert dead.count() == 1
        assert deleted in dead

    def test_alive_filter_on_queryset(self) -> None:
        """alive() on queryset should return non-deleted records."""
        active = OrganizationFactory.create()
        deleted = OrganizationFactory.create()
        deleted.soft_delete()

        alive = Organization.all_objects.get_queryset().alive()

        assert alive.count() == 1
        assert active in alive


@pytest.mark.django_db
class TestMemberSoftDelete:
    """Tests for soft delete on Member model."""

    def test_member_soft_delete(self) -> None:
        """Member model should support soft delete."""
        member = MemberFactory.create()

        member.soft_delete()

        member.refresh_from_db()
        assert member.is_deleted is True

    def test_member_restore(self) -> None:
        """Member model should support restore."""
        member = MemberFactory.create()
        member.soft_delete()

        member.restore()

        member.refresh_from_db()
        assert member.is_deleted is False

    def test_deleted_member_not_in_default_queryset(self) -> None:
        """Soft-deleted members should not appear in default queries."""
        active_member = MemberFactory.create()
        deleted_member = MemberFactory.create()
        deleted_member.soft_delete()

        members = Member.objects.all()

        assert members.count() == 1
        assert active_member in members
        assert deleted_member not in members

    def test_deleted_member_accessible_via_all_objects(self) -> None:
        """Soft-deleted members should be accessible via all_objects."""
        _active_member = MemberFactory.create()
        deleted_member = MemberFactory.create()
        deleted_member.soft_delete()

        all_members = Member.all_objects.all()

        assert all_members.count() == 2
        assert deleted_member in all_members

    def test_unique_constraint_allows_reactivation(self) -> None:
        """Soft-deleted member should allow same user/org to create new membership."""
        user = UserFactory.create()
        org = OrganizationFactory.create()
        old_member = MemberFactory.create(user=user, organization=org)
        old_member.soft_delete()

        new_member = MemberFactory.create(user=user, organization=org)

        assert new_member.pk is not None
        assert new_member.pk != old_member.pk
        assert Member.all_objects.filter(user=user, organization=org).count() == 2


@pytest.mark.django_db
class TestOrganizationSoftDelete:
    """Tests for soft delete on Organization model."""

    def test_organization_soft_delete(self) -> None:
        """Organization model should support soft delete."""
        org = OrganizationFactory.create()

        org.soft_delete()

        org.refresh_from_db()
        assert org.is_deleted is True

    def test_organization_restore(self) -> None:
        """Organization model should support restore."""
        org = OrganizationFactory.create()
        org.soft_delete()

        org.restore()

        org.refresh_from_db()
        assert org.is_deleted is False

    def test_deleted_org_not_in_default_queryset(self) -> None:
        """Soft-deleted orgs should not appear in default queries."""
        active_org = OrganizationFactory.create()
        deleted_org = OrganizationFactory.create()
        deleted_org.soft_delete()

        orgs = Organization.objects.all()

        assert orgs.count() == 1
        assert active_org in orgs
        assert deleted_org not in orgs
