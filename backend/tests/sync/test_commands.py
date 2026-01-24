"""
Tests for sync management commands.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.sync.models import SyncOperation
from tests.accounts.factories import OrganizationFactory
from tests.sync.conftest import SyncTestContact
from tests.sync.factories import SyncOperationFactory


@pytest.mark.django_db
class TestCleanupTombstones:
    """Tests for cleanup_tombstones command."""

    def test_dry_run_shows_count_without_deleting(self, sync_registry, test_contact_factory):
        """Dry run should show what would be deleted without deleting."""
        org = OrganizationFactory.create()

        # Create old tombstone
        contact = test_contact_factory(organization=org, name="Old Deleted")
        contact.soft_delete()

        # Make it old by patching deleted_at
        old_date = timezone.now() - timedelta(days=100)
        contact.deleted_at = old_date
        contact.save(update_fields=["deleted_at"])

        out = StringIO()
        call_command("cleanup_tombstones", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "DRY RUN" in output
        assert "1 tombstones would be removed" in output

        # Contact should still exist
        contact.refresh_from_db()
        assert contact.deleted_at is not None

    def test_deletes_old_tombstones(self, sync_registry, test_contact_factory):
        """Should hard-delete tombstones past retention period."""
        org = OrganizationFactory.create()

        # Create old tombstone
        contact = test_contact_factory(organization=org, name="Old Deleted")
        contact.soft_delete()

        old_date = timezone.now() - timedelta(days=100)
        contact.deleted_at = old_date
        contact.save(update_fields=["deleted_at"])

        contact_id = contact.id

        out = StringIO()
        call_command("cleanup_tombstones", "--retention-days=90", stdout=out)

        output = out.getvalue()
        assert "1 tombstones removed" in output

        # Contact should be hard-deleted
        assert not SyncTestContact.all_objects.filter(id=contact_id).exists()

    def test_preserves_recent_tombstones(self, sync_registry, test_contact_factory):
        """Should not delete tombstones within retention period."""
        org = OrganizationFactory.create()

        # Create recent tombstone
        contact = test_contact_factory(organization=org, name="Recent Deleted")
        contact.soft_delete()

        contact_id = contact.id

        out = StringIO()
        call_command("cleanup_tombstones", "--retention-days=90", stdout=out)

        output = out.getvalue()
        assert "0 tombstones to remove" in output

        # Contact should still exist
        assert SyncTestContact.all_objects.filter(id=contact_id).exists()

    def test_filters_by_entity_type(self, sync_registry, test_contact_factory):
        """Should filter by entity type when specified."""
        org = OrganizationFactory.create()

        contact = test_contact_factory(organization=org, name="Deleted")
        contact.soft_delete()

        old_date = timezone.now() - timedelta(days=100)
        contact.deleted_at = old_date
        contact.save(update_fields=["deleted_at"])

        out = StringIO()
        call_command(
            "cleanup_tombstones",
            "--entity-type=test_contact",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        assert "test_contact" in output

    def test_unknown_entity_type_error(self, sync_registry):
        """Should error for unknown entity type."""
        out = StringIO()
        err = StringIO()
        call_command(
            "cleanup_tombstones",
            "--entity-type=nonexistent",
            stdout=out,
            stderr=err,
        )

        assert "Unknown entity type" in err.getvalue()


@pytest.mark.django_db
class TestBackfillFieldTimestamps:
    """Tests for backfill_field_timestamps command."""

    def test_dry_run_shows_count_without_updating(self, sync_registry, test_contact_factory):
        """Dry run should show what would be updated without updating."""
        org = OrganizationFactory.create()

        # Create contact with empty field_timestamps
        contact = test_contact_factory(organization=org, name="No Timestamps")
        contact.field_timestamps = {}
        contact.save(update_fields=["field_timestamps"])

        out = StringIO()
        call_command("backfill_field_timestamps", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "DRY RUN" in output
        assert "1 entities to backfill" in output

        # Contact should still have empty timestamps
        contact.refresh_from_db()
        assert contact.field_timestamps == {}

    def test_backfills_empty_timestamps(self, sync_registry, test_contact_factory):
        """Should backfill field_timestamps from updated_at."""
        org = OrganizationFactory.create()

        contact = test_contact_factory(
            organization=org,
            name="Needs Backfill",
            email="test@example.com",
        )
        contact.field_timestamps = {}
        contact.save(update_fields=["field_timestamps"])

        out = StringIO()
        call_command("backfill_field_timestamps", stdout=out)

        output = out.getvalue()
        assert "1 entities backfilled" in output

        contact.refresh_from_db()
        assert "name" in contact.field_timestamps
        assert "email" in contact.field_timestamps

    def test_skips_already_backfilled(self, sync_registry, test_contact_factory):
        """Should skip entities that already have timestamps."""
        from django.utils import timezone

        org = OrganizationFactory.create()

        contact = test_contact_factory(organization=org, name="Has Timestamps")
        # Manually set timestamps to simulate already backfilled
        contact.field_timestamps = {"name": timezone.now().isoformat()}
        contact.save(update_fields=["field_timestamps"])

        out = StringIO()
        call_command("backfill_field_timestamps", stdout=out)

        output = out.getvalue()
        assert "0 entities need backfill" in output

    def test_filters_by_entity_type(self, sync_registry, test_contact_factory):
        """Should filter by entity type when specified."""
        org = OrganizationFactory.create()

        contact = test_contact_factory(organization=org, name="Test")
        contact.field_timestamps = {}
        contact.save(update_fields=["field_timestamps"])

        out = StringIO()
        call_command(
            "backfill_field_timestamps",
            "--entity-type=test_contact",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        assert "SyncTestContact" in output

    def test_unknown_entity_type_error(self, sync_registry):
        """Should error for unknown entity type."""
        out = StringIO()
        err = StringIO()
        call_command(
            "backfill_field_timestamps",
            "--entity-type=nonexistent",
            stdout=out,
            stderr=err,
        )

        assert "Unknown entity type" in err.getvalue()


@pytest.mark.django_db
class TestCleanupSyncOperations:
    """Tests for cleanup_sync_operations command."""

    def test_dry_run_shows_count_without_deleting(self):
        """Dry run should show what would be deleted without deleting."""
        # Create old sync operation
        old_date = timezone.now() - timedelta(days=400)
        op = SyncOperationFactory.create(status=SyncOperation.Status.APPLIED)
        SyncOperation.objects.filter(id=op.id).update(server_timestamp=old_date)

        out = StringIO()
        call_command("cleanup_sync_operations", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "DRY RUN" in output
        assert "1" in output
        assert "would be removed" in output

        # Operation should still exist
        assert SyncOperation.objects.filter(id=op.id).exists()

    def test_deletes_old_operations(self):
        """Should delete operations past retention period."""
        old_date = timezone.now() - timedelta(days=400)
        op = SyncOperationFactory.create(status=SyncOperation.Status.APPLIED)
        SyncOperation.objects.filter(id=op.id).update(server_timestamp=old_date)

        op_id = op.id

        out = StringIO()
        call_command("cleanup_sync_operations", "--retention-days=365", stdout=out)

        output = out.getvalue()
        assert "1 sync operations removed" in output

        # Operation should be deleted
        assert not SyncOperation.objects.filter(id=op_id).exists()

    def test_preserves_recent_operations(self):
        """Should not delete operations within retention period."""
        op = SyncOperationFactory.create(status=SyncOperation.Status.APPLIED)

        out = StringIO()
        call_command("cleanup_sync_operations", "--retention-days=365", stdout=out)

        output = out.getvalue()
        assert "No sync operations to remove" in output

        # Operation should still exist
        assert SyncOperation.objects.filter(id=op.id).exists()

    def test_filters_by_status(self):
        """Should filter by status when specified."""
        old_date = timezone.now() - timedelta(days=400)

        op_applied = SyncOperationFactory.create(status=SyncOperation.Status.APPLIED)
        op_rejected = SyncOperationFactory.create(status=SyncOperation.Status.REJECTED)

        SyncOperation.objects.filter(id__in=[op_applied.id, op_rejected.id]).update(
            server_timestamp=old_date
        )

        out = StringIO()
        call_command(
            "cleanup_sync_operations",
            "--retention-days=365",
            "--status=applied",
            stdout=out,
        )

        output = out.getvalue()
        assert "1 sync operations removed" in output

        # Only applied should be deleted
        assert not SyncOperation.objects.filter(id=op_applied.id).exists()
        assert SyncOperation.objects.filter(id=op_rejected.id).exists()

    def test_batch_deletion(self):
        """Should delete in batches."""
        old_date = timezone.now() - timedelta(days=400)

        # Create multiple operations
        ops = [SyncOperationFactory.create() for _ in range(5)]
        SyncOperation.objects.filter(id__in=[op.id for op in ops]).update(server_timestamp=old_date)

        out = StringIO()
        call_command(
            "cleanup_sync_operations",
            "--retention-days=365",
            "--batch-size=2",
            stdout=out,
        )

        output = out.getvalue()
        assert "5 sync operations removed" in output

        # All should be deleted
        assert SyncOperation.objects.filter(id__in=[op.id for op in ops]).count() == 0

    def test_dry_run_shows_status_breakdown(self):
        """Dry run should show breakdown by status."""
        old_date = timezone.now() - timedelta(days=400)

        SyncOperationFactory.create(status=SyncOperation.Status.APPLIED)
        SyncOperationFactory.create(status=SyncOperation.Status.APPLIED)
        SyncOperationFactory.create(status=SyncOperation.Status.REJECTED)

        SyncOperation.objects.all().update(server_timestamp=old_date)

        out = StringIO()
        call_command("cleanup_sync_operations", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "Breakdown by status" in output
        assert "applied" in output
        assert "rejected" in output
