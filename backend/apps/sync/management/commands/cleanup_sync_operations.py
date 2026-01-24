"""
Management command to delete old SyncOperation records.

SyncOperation records are kept for auditing and debugging purposes.
After a retention period, they can be permanently removed to prevent
unbounded table growth.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.sync.models import SyncOperation


class Command(BaseCommand):
    """Delete SyncOperation records older than retention period."""

    help = "Remove old sync operation audit records past retention period"

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-days",
            type=int,
            default=getattr(settings, "SYNC_OPERATION_RETENTION_DAYS", 365),
            help="Days to retain sync operations (default: 365)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10000,
            help="Number of records to delete per batch (default: 10000)",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["applied", "rejected", "duplicate", "conflict", "pending"],
            default=None,
            help="Only clean up operations with specific status",
        )

    def handle(self, *args, **options):
        retention_days = options["retention_days"]
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        status_filter = options["status"]

        cutoff = timezone.now() - timedelta(days=retention_days)

        self.stdout.write(
            f"Cleaning sync operations older than {retention_days} days "
            f"(before {cutoff.isoformat()})"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        # Build queryset
        qs = SyncOperation.objects.filter(server_timestamp__lt=cutoff)

        if status_filter:
            qs = qs.filter(status=status_filter)
            self.stdout.write(f"Filtering by status: {status_filter}")

        total_count = qs.count()

        if total_count == 0:
            self.stdout.write("No sync operations to remove")
            return

        self.stdout.write(f"Found {total_count} sync operations to remove")

        if dry_run:
            # Show breakdown by status
            self._show_status_breakdown(qs)
            self.stdout.write(
                self.style.SUCCESS(f"\nTotal: {total_count} operations would be removed")
            )
            return

        # Delete in batches to avoid long-running transactions
        total_deleted = 0
        while True:
            # Get batch of IDs to delete
            batch_ids = list(qs.values_list("id", flat=True)[:batch_size])

            if not batch_ids:
                break

            deleted_count, _ = SyncOperation.objects.filter(id__in=batch_ids).delete()
            total_deleted += deleted_count

            self.stdout.write(f"  Deleted {total_deleted}/{total_count} operations...")

        self.stdout.write(self.style.SUCCESS(f"\nTotal: {total_deleted} sync operations removed"))

    def _show_status_breakdown(self, qs):
        """Show count breakdown by status for dry run."""
        from django.db.models import Count

        breakdown = qs.values("status").annotate(count=Count("id")).order_by("-count")

        self.stdout.write("\nBreakdown by status:")
        for row in breakdown:
            self.stdout.write(f"  {row['status']}: {row['count']}")
