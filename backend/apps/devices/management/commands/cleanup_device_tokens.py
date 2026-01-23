"""
Management command to clean up expired and used device link tokens.

Run periodically via cron or scheduled task to prevent database bloat.
Example: ./manage.py cleanup_device_tokens --days 7
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.devices.models import DeviceLinkToken


class Command(BaseCommand):
    help = "Delete expired and used device link tokens older than specified days"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Delete tokens older than this many days (default: 7)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        cutoff_date = timezone.now() - timedelta(days=days)

        # Find tokens that are either:
        # 1. Used (used_at is not null) AND older than cutoff
        # 2. Expired (expires_at < now) AND older than cutoff
        tokens_to_delete = DeviceLinkToken.objects.filter(
            Q(used_at__isnull=False) | Q(expires_at__lt=timezone.now()),
            created_at__lt=cutoff_date,
        )

        count = tokens_to_delete.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY RUN] Would delete {count} device link tokens")
            )
        else:
            deleted, _ = tokens_to_delete.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully deleted {deleted} device link tokens")
            )
