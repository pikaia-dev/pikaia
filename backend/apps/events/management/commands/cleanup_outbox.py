"""
Cleanup outbox events management command.

Removes old published events and optionally failed events to prevent
unbounded table growth. Designed to run as a scheduled job (e.g., daily cron).

Best practice: Published events can be deleted after a short retention period
(default 7 days) since they've already been delivered. Failed events are kept
longer (default 30 days) for debugging.
"""

from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from django.utils import timezone

from apps.core.logging import get_logger
from apps.events.models import OutboxEvent

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Clean up old outbox events to prevent unbounded table growth"

    def add_arguments(self, parser):
        parser.add_argument(
            "--published-retention-days",
            type=int,
            default=7,
            help="Delete published events older than N days (default: 7)",
        )
        parser.add_argument(
            "--failed-retention-days",
            type=int,
            default=30,
            help="Delete failed events older than N days (default: 30)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Delete in batches of N to avoid long locks (default: 1000)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        published_retention_days = options["published_retention_days"]
        failed_retention_days = options["failed_retention_days"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        now = timezone.now()
        published_cutoff = now - timezone.timedelta(days=published_retention_days)
        failed_cutoff = now - timezone.timedelta(days=failed_retention_days)

        logger.info(
            "outbox_cleanup_started",
            published_retention_days=published_retention_days,
            failed_retention_days=failed_retention_days,
            published_cutoff=published_cutoff.isoformat(),
            failed_cutoff=failed_cutoff.isoformat(),
            dry_run=dry_run,
        )

        # Clean up published events (short retention - already delivered)
        published_deleted = self._cleanup_events(
            status=OutboxEvent.Status.PUBLISHED,
            cutoff=published_cutoff,
            batch_size=batch_size,
            dry_run=dry_run,
        )

        # Clean up failed events (longer retention - useful for debugging)
        failed_deleted = self._cleanup_events(
            status=OutboxEvent.Status.FAILED,
            cutoff=failed_cutoff,
            batch_size=batch_size,
            dry_run=dry_run,
        )

        total_deleted = published_deleted + failed_deleted

        logger.info(
            "outbox_cleanup_completed",
            published_deleted=published_deleted,
            failed_deleted=failed_deleted,
            total_deleted=total_deleted,
            dry_run=dry_run,
        )

        if dry_run:
            self.stdout.write(
                f"DRY RUN: Would delete {published_deleted} published and "
                f"{failed_deleted} failed events ({total_deleted} total)"
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {published_deleted} published and "
                    f"{failed_deleted} failed events ({total_deleted} total)"
                )
            )

    def _cleanup_events(
        self,
        status: str,
        cutoff: timezone.datetime,
        batch_size: int,
        dry_run: bool,
    ) -> int:
        """
        Delete events of given status older than cutoff date.

        Deletes in batches to avoid long-running transactions and table locks.
        Returns total number of events deleted.
        """
        queryset: QuerySet[OutboxEvent] = OutboxEvent.objects.filter(
            status=status,
            created_at__lt=cutoff,
        )

        if dry_run:
            return queryset.count()

        total_deleted = 0
        while True:
            # Get batch of IDs to delete
            ids_to_delete = list(queryset.values_list("id", flat=True)[:batch_size])
            if not ids_to_delete:
                break

            deleted_count, _ = OutboxEvent.objects.filter(id__in=ids_to_delete).delete()
            total_deleted += deleted_count

            logger.debug(
                "outbox_cleanup_batch",
                status=status,
                batch_deleted=deleted_count,
                total_deleted=total_deleted,
            )

        return total_deleted
