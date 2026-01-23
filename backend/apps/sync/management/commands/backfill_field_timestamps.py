"""
Management command to backfill field_timestamps for existing entities.

When field-level LWW is added to existing entities, their field_timestamps
will be empty. This command initializes them to the entity's updated_at,
treating all fields as having been modified at the same time.
"""

from django.core.management.base import BaseCommand

from apps.sync.models import FieldLevelLWWMixin
from apps.sync.registry import SyncRegistry


class Command(BaseCommand):
    """Initialize field_timestamps from entity updated_at for existing records."""

    help = "Backfill field_timestamps for existing sync entities"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without actually updating",
        )
        parser.add_argument(
            "--entity-type",
            type=str,
            default=None,
            help="Only backfill specific entity type",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of records to process per batch (default: 1000)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        entity_type_filter = options["entity_type"]
        batch_size = options["batch_size"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        total_updated = 0

        # Get LWW models to process
        lww_models = SyncRegistry.get_lww_models()

        if entity_type_filter:
            if not SyncRegistry.is_registered(entity_type_filter):
                self.stderr.write(
                    self.style.ERROR(f"Unknown entity type: {entity_type_filter}")
                )
                return

            model = SyncRegistry.get_model(entity_type_filter)
            if not issubclass(model, FieldLevelLWWMixin):
                self.stderr.write(
                    self.style.ERROR(
                        f"{entity_type_filter} does not use field-level LWW"
                    )
                )
                return

            lww_models = [model]

        for model in lww_models:
            model_name = model.__name__

            # Get syncable fields for this model
            syncable_fields = model.get_syncable_fields()

            if not syncable_fields:
                self.stdout.write(f"  {model_name}: no syncable fields, skipping")
                continue

            # Find entities with empty field_timestamps
            entities_to_update = model.all_objects.filter(field_timestamps={})
            total_count = entities_to_update.count()

            if total_count == 0:
                self.stdout.write(f"  {model_name}: 0 entities need backfill")
                continue

            self.stdout.write(f"  {model_name}: {total_count} entities to backfill")

            if dry_run:
                total_updated += total_count
                continue

            # Process in batches
            updated_count = 0
            processed = 0

            while processed < total_count:
                # Get batch of entity IDs (re-query to handle concurrent changes)
                batch_ids = list(
                    model.all_objects.filter(field_timestamps={})
                    .values_list("id", flat=True)[:batch_size]
                )

                if not batch_ids:
                    break

                # Update each entity in the batch
                for entity_id in batch_ids:
                    try:
                        entity = model.all_objects.get(id=entity_id)

                        # Skip if already backfilled (race condition)
                        if entity.field_timestamps:
                            continue

                        # Initialize all fields to entity's updated_at
                        entity.field_timestamps = {
                            field: entity.updated_at.isoformat()
                            for field in syncable_fields
                        }
                        entity.save(update_fields=["field_timestamps"])
                        updated_count += 1

                    except model.DoesNotExist:
                        # Entity was deleted between query and update
                        pass

                processed += len(batch_ids)
                self.stdout.write(
                    f"    Processed {processed}/{total_count} "
                    f"(updated {updated_count})"
                )

            self.stdout.write(
                self.style.SUCCESS(f"  {model_name}: {updated_count} entities backfilled")
            )
            total_updated += updated_count

        action = "would be" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(f"\nTotal: {total_updated} entities {action} backfilled")
        )
