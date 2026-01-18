"""
Generate audit log schema for Lambda consumer.

This command generates a Python module containing:
- Table name and field names from the Django AuditLog model
- INSERT SQL for the Lambda consumer
- Audit-worthy event types (single source of truth)

Run this in CI before deploying Lambda to ensure schema stays in sync.

Usage:
    uv run python manage.py generate_audit_schema
    uv run python manage.py generate_audit_schema --check  # CI validation

Maintenance:
    When adding new audit-worthy event types:
    1. Add the event type to AUDIT_EVENT_TYPES below
    2. Run this command to regenerate the schema
    3. Update AUDIT_EVENT_TYPES in infra/stacks/events_stack.py to match
       (CDK can't import Django code, so manual sync is required)
    4. CI validates the generated schema is up-to-date
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.events.models import AuditLog

# Single source of truth for audit-worthy event types
AUDIT_EVENT_TYPES = {
    # Member management
    "member.invited",
    "member.bulk_invited",
    "member.role_changed",
    "member.removed",
    "member.joined",
    # Organization
    "organization.created",
    "organization.updated",
    "organization.billing_updated",
    # User
    "user.profile_updated",
    "user.phone_changed",
}


class Command(BaseCommand):
    help = "Generate audit schema for Lambda consumer"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="infra/functions/audit-consumer/generated_schema.py",
            help="Output path for generated schema (relative to project root)",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Check if generated schema is up-to-date (for CI)",
        )

    def handle(self, *args, **options):
        # Get concrete fields from model (excludes relations)
        fields = []
        for f in AuditLog._meta.concrete_fields:
            if f.name == "id":
                continue  # Skip auto-generated id
            fields.append(f.name)

        table_name = AuditLog._meta.db_table

        # Generate INSERT SQL with ON CONFLICT for idempotency
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(fields)

        insert_sql = f"""INSERT INTO {table_name} (id, {columns})
VALUES (gen_random_uuid(), {placeholders})
ON CONFLICT (event_id) DO NOTHING"""  # nosec B608 - table_name from Django model meta, not user input

        # Generate Python module (includes event types for single source of truth)
        output_content = f'''"""
Auto-generated audit schema from Django model.
DO NOT EDIT - run: uv run python manage.py generate_audit_schema
"""

TABLE_NAME = "{table_name}"

FIELDS = {json.dumps(fields, indent=4)}

INSERT_SQL = """{insert_sql}"""

# Audit-worthy event types (single source of truth)
AUDIT_EVENT_TYPES = {json.dumps(sorted(AUDIT_EVENT_TYPES), indent=4)}
'''

        # Resolve path relative to project root (backend's parent)
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        project_root = backend_dir.parent
        output_path = project_root / options["output"]

        if options["check"]:
            if not output_path.exists():
                self.stderr.write(self.style.ERROR(f"Schema file missing: {output_path}"))
                self.stderr.write("Run: uv run python manage.py generate_audit_schema")
                exit(1)

            existing = output_path.read_text()
            if existing != output_content:
                self.stderr.write(self.style.ERROR("Schema out of date!"))
                self.stderr.write("Run: uv run python manage.py generate_audit_schema")
                exit(1)

            self.stdout.write(self.style.SUCCESS("Schema is up-to-date"))
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_content)
            self.stdout.write(self.style.SUCCESS(f"Generated: {output_path}"))
