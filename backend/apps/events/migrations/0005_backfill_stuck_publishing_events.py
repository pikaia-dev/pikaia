"""
One-time data migration: reset any legacy 'publishing' rows with NULL claimed_at
back to 'pending'.

These rows were created before the claimed_at column existed and cannot be
recovered by the Lambda's runtime recovery query (which now requires
claimed_at IS NOT NULL). Without this backfill they would remain stuck
in 'publishing' forever.
"""

from django.db import migrations


def reset_legacy_publishing_events(apps, schema_editor):
    OutboxEvent = apps.get_model("events", "OutboxEvent")
    updated = OutboxEvent.objects.filter(
        status="publishing",
        claimed_at__isnull=True,
    ).update(status="pending")
    if updated:
        print(f"  Reset {updated} legacy publishing events to pending")


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0004_add_claimed_at_to_outboxevent"),
    ]

    operations = [
        migrations.RunPython(
            reset_legacy_publishing_events,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
