"""
Tests for cleanup_outbox management command.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.events.models import OutboxEvent


def _create_event(status: str, days_old: int) -> OutboxEvent:
    """Helper to create an OutboxEvent with a specific age."""
    event = OutboxEvent.objects.create(
        event_type="test.event",
        aggregate_type="test",
        aggregate_id="test_123",
        organization_id="org_456",
        payload={"data": {}},
        status=status,
    )
    # Manually set created_at since auto_now_add can't be overridden
    OutboxEvent.objects.filter(id=event.id).update(
        created_at=timezone.now() - timezone.timedelta(days=days_old)
    )
    return event


@pytest.mark.django_db
class TestCleanupOutboxCommand:
    """Tests for the cleanup_outbox management command."""

    def test_deletes_old_published_events(self):
        """Published events older than retention period are deleted."""
        # Create events: 10 days old (should be deleted) and 3 days old (should remain)
        old_event = _create_event(OutboxEvent.Status.PUBLISHED, days_old=10)
        recent_event = _create_event(OutboxEvent.Status.PUBLISHED, days_old=3)

        call_command("cleanup_outbox", "--published-retention-days=7")

        assert not OutboxEvent.objects.filter(id=old_event.id).exists()
        assert OutboxEvent.objects.filter(id=recent_event.id).exists()

    def test_deletes_old_failed_events(self):
        """Failed events older than retention period are deleted."""
        old_event = _create_event(OutboxEvent.Status.FAILED, days_old=35)
        recent_event = _create_event(OutboxEvent.Status.FAILED, days_old=10)

        call_command("cleanup_outbox", "--failed-retention-days=30")

        assert not OutboxEvent.objects.filter(id=old_event.id).exists()
        assert OutboxEvent.objects.filter(id=recent_event.id).exists()

    def test_does_not_delete_pending_events(self):
        """Pending events are never deleted regardless of age."""
        old_pending = _create_event(OutboxEvent.Status.PENDING, days_old=100)

        call_command("cleanup_outbox")

        assert OutboxEvent.objects.filter(id=old_pending.id).exists()

    def test_dry_run_does_not_delete(self):
        """Dry run mode reports counts but doesn't delete."""
        old_event = _create_event(OutboxEvent.Status.PUBLISHED, days_old=10)
        stdout = StringIO()

        call_command("cleanup_outbox", "--dry-run", stdout=stdout)

        assert OutboxEvent.objects.filter(id=old_event.id).exists()
        assert "DRY RUN" in stdout.getvalue()
        assert "Would delete 1 published" in stdout.getvalue()

    def test_respects_custom_retention_days(self):
        """Custom retention periods are respected."""
        # 5 days old - should be deleted with 3-day retention
        event = _create_event(OutboxEvent.Status.PUBLISHED, days_old=5)

        call_command("cleanup_outbox", "--published-retention-days=3")

        assert not OutboxEvent.objects.filter(id=event.id).exists()

    def test_batch_deletion(self):
        """Events are deleted in batches to avoid long locks."""
        # Create multiple old events
        for _ in range(5):
            _create_event(OutboxEvent.Status.PUBLISHED, days_old=10)

        # Delete with small batch size
        call_command("cleanup_outbox", "--batch-size=2")

        # All should be deleted despite batch size
        assert OutboxEvent.objects.filter(status=OutboxEvent.Status.PUBLISHED).count() == 0

    def test_reports_deletion_counts(self):
        """Command outputs the count of deleted events."""
        _create_event(OutboxEvent.Status.PUBLISHED, days_old=10)
        _create_event(OutboxEvent.Status.PUBLISHED, days_old=10)
        _create_event(OutboxEvent.Status.FAILED, days_old=35)
        stdout = StringIO()

        call_command("cleanup_outbox", stdout=stdout)

        output = stdout.getvalue()
        assert "2 published" in output
        assert "1 failed" in output
        assert "3 total" in output
