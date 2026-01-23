"""
Management command to hard-delete tombstones older than retention period.

Tombstones (soft-deleted sync records) are kept for a retention period
to allow late-syncing clients to receive deletion notifications.
After that period, they can be permanently removed.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.sync.registry import SyncRegistry


class Command(BaseCommand):
    """Hard-delete tombstones older than retention period."""

    help = "Remove soft-deleted sync entities past retention period"

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-days",
            type=int,
            default=getattr(settings, "SYNC_TOMBSTONE_RETENTION_DAYS", 90),
            help="Days to retain tombstones (default: 90)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--entity-type",
            type=str,
            default=None,
            help="Only clean up specific entity type",
        )

    def handle(self, *args, **options):
        retention_days = options["retention_days"]
        dry_run = options["dry_run"]
        entity_type_filter = options["entity_type"]

        cutoff = timezone.now() - timedelta(days=retention_days)

        self.stdout.write(
            f"Cleaning tombstones older than {retention_days} days (before {cutoff.isoformat()})"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        total_deleted = 0

        # Get models to process
        if entity_type_filter:
            if not SyncRegistry.is_registered(entity_type_filter):
                self.stderr.write(self.style.ERROR(f"Unknown entity type: {entity_type_filter}"))
                return

            models_to_process = [(entity_type_filter, SyncRegistry.get_model(entity_type_filter))]
        else:
            models_to_process = [
                (et, SyncRegistry.get_model(et)) for et in SyncRegistry.get_all_entity_types()
            ]

        for entity_type, model in models_to_process:
            # Find tombstones past retention
            tombstones = model.all_objects.filter(
                deleted_at__isnull=False,
                deleted_at__lt=cutoff,
            )
            count = tombstones.count()

            if count == 0:
                self.stdout.write(f"  {entity_type}: 0 tombstones to remove")
                continue

            if not dry_run:
                # Use hard_delete to permanently remove
                deleted_count, _ = tombstones.hard_delete()
                self.stdout.write(
                    self.style.SUCCESS(f"  {entity_type}: {deleted_count} tombstones removed")
                )
                total_deleted += deleted_count
            else:
                self.stdout.write(f"  {entity_type}: {count} tombstones would be removed")
                total_deleted += count

        action = "would be" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(f"\nTotal: {total_deleted} tombstones {action} removed")
        )
