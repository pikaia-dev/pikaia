"""
Tests for generate_audit_schema management command.
"""

import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.events.management.commands.generate_audit_schema import AUDIT_EVENT_TYPES


class TestGenerateAuditSchema:
    """Tests for the generate_audit_schema management command."""

    def test_audit_event_types_defined(self):
        """Verify AUDIT_EVENT_TYPES contains expected event types."""
        # Should have member events
        assert "member.invited" in AUDIT_EVENT_TYPES
        assert "member.removed" in AUDIT_EVENT_TYPES
        assert "member.role_changed" in AUDIT_EVENT_TYPES

        # Should have organization events
        assert "organization.created" in AUDIT_EVENT_TYPES
        assert "organization.updated" in AUDIT_EVENT_TYPES
        assert "organization.billing_updated" in AUDIT_EVENT_TYPES

        # Should have user events
        assert "user.profile_updated" in AUDIT_EVENT_TYPES
        assert "user.phone_changed" in AUDIT_EVENT_TYPES

    def test_generates_schema_file(self):
        """Test that command generates a valid Python schema file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated_schema.py"

            call_command("generate_audit_schema", output=str(output_path))

            assert output_path.exists()
            content = output_path.read_text()

            # Check required components
            assert "TABLE_NAME" in content
            assert "FIELDS" in content
            assert "INSERT_SQL" in content
            assert "AUDIT_EVENT_TYPES" in content
            assert "events_auditlog" in content  # Table name
            assert "ON CONFLICT (event_id) DO NOTHING" in content  # Idempotency

    def test_generated_fields_match_model(self):
        """Test that generated FIELDS matches AuditLog model fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated_schema.py"

            call_command("generate_audit_schema", output=str(output_path))

            content = output_path.read_text()

            # Check key fields are present
            assert '"event_id"' in content
            assert '"action"' in content
            assert '"aggregate_type"' in content
            assert '"aggregate_id"' in content
            assert '"organization_id"' in content
            assert '"actor_id"' in content
            assert '"actor_email"' in content
            assert '"correlation_id"' in content
            assert '"ip_address"' in content
            assert '"user_agent"' in content
            assert '"diff"' in content
            assert '"metadata"' in content
            assert '"created_at"' in content

    def test_check_flag_passes_when_up_to_date(self):
        """Test --check passes when schema is up to date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated_schema.py"

            # Generate the schema
            call_command("generate_audit_schema", output=str(output_path))

            # Check should pass (no exception)
            call_command("generate_audit_schema", output=str(output_path), check=True)

    def test_check_flag_fails_when_missing(self):
        """Test --check fails when schema file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nonexistent_schema.py"

            with pytest.raises(SystemExit) as exc_info:
                call_command("generate_audit_schema", output=str(output_path), check=True)

            assert exc_info.value.code == 1

    def test_check_flag_fails_when_outdated(self):
        """Test --check fails when schema content differs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated_schema.py"

            # Write outdated content
            output_path.write_text("# outdated schema")

            with pytest.raises(SystemExit) as exc_info:
                call_command("generate_audit_schema", output=str(output_path), check=True)

            assert exc_info.value.code == 1

    def test_schema_includes_all_audit_event_types(self):
        """Test that generated schema includes all AUDIT_EVENT_TYPES."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated_schema.py"

            call_command("generate_audit_schema", output=str(output_path))

            content = output_path.read_text()

            for event_type in AUDIT_EVENT_TYPES:
                assert f'"{event_type}"' in content, f"Missing event type: {event_type}"
