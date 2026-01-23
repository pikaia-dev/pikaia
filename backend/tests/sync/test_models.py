"""
Tests for sync models.
"""

from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from apps.sync.models import FieldLevelLWWMixin, SyncOperation
from tests.accounts.factories import MemberFactory, OrganizationFactory
from tests.sync.factories import SyncOperationFactory


@pytest.mark.django_db
class TestSyncOperation:
    """Tests for SyncOperation model."""

    def test_create_sync_operation(self):
        """Should create a sync operation with all fields."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        op = SyncOperation.objects.create(
            idempotency_key="op_123456",
            organization=org,
            actor=member,
            device_id="device_abc",
            entity_type="contact",
            entity_id="ct_01HN8J123",
            intent=SyncOperation.Intent.CREATE,
            payload={"name": "Alice"},
            client_timestamp=timezone.now(),
            status=SyncOperation.Status.PENDING,
        )

        assert op.id is not None
        assert op.idempotency_key == "op_123456"
        assert op.server_timestamp is not None

    def test_idempotency_key_unique(self):
        """Should enforce unique idempotency keys."""
        from django.db import IntegrityError

        _op1 = SyncOperationFactory.create(idempotency_key="duplicate_key")

        with pytest.raises(IntegrityError):
            SyncOperationFactory.create(idempotency_key="duplicate_key")

    def test_str_representation(self):
        """Should have a readable string representation."""
        op = SyncOperationFactory.create(
            entity_type="contact",
            entity_id="ct_123",
            intent=SyncOperation.Intent.UPDATE,
            status=SyncOperation.Status.APPLIED,
        )

        str_repr = str(op)
        assert "update" in str_repr
        assert "contact" in str_repr
        assert "ct_123" in str_repr
        assert "applied" in str_repr

    def test_calculate_drift_ms(self):
        """Should calculate drift between client and server timestamps."""
        past_time = timezone.now() - timedelta(seconds=5)
        op = SyncOperationFactory.create(client_timestamp=past_time)

        drift = op.calculate_drift_ms()

        # Drift should be approximately 5000ms (5 seconds)
        assert 4900 <= drift <= 5500

    def test_intent_choices(self):
        """Should support create, update, delete intents."""
        op_create = SyncOperationFactory.create(intent=SyncOperation.Intent.CREATE)
        op_update = SyncOperationFactory.create(intent=SyncOperation.Intent.UPDATE)
        op_delete = SyncOperationFactory.create(intent=SyncOperation.Intent.DELETE)

        assert op_create.intent == "create"
        assert op_update.intent == "update"
        assert op_delete.intent == "delete"

    def test_status_choices(self):
        """Should support all status values."""
        statuses = [
            SyncOperation.Status.PENDING,
            SyncOperation.Status.APPLIED,
            SyncOperation.Status.REJECTED,
            SyncOperation.Status.CONFLICT,
            SyncOperation.Status.DUPLICATE,
        ]

        for status in statuses:
            op = SyncOperationFactory.create(status=status)
            assert op.status == status

    def test_resolution_details_nullable(self):
        """Should allow null resolution_details."""
        op = SyncOperationFactory.create(resolution_details=None)
        assert op.resolution_details is None

    def test_resolution_details_json(self):
        """Should store resolution_details as JSON."""
        details = {"error": "VALIDATION_ERROR", "fields": ["email"]}
        op = SyncOperationFactory.create(resolution_details=details)

        op.refresh_from_db()
        assert op.resolution_details == details

    def test_conflict_fields_json(self):
        """Should store conflict_fields as JSON array."""
        conflicts = ["name", "phone"]
        op = SyncOperationFactory.create(conflict_fields=conflicts)

        op.refresh_from_db()
        assert op.conflict_fields == conflicts

    def test_drift_ms_nullable(self):
        """Should allow null drift_ms."""
        op = SyncOperationFactory.create(drift_ms=None)
        assert op.drift_ms is None

    def test_ordering_by_server_timestamp_desc(self):
        """Should order by server_timestamp descending by default."""
        _op1 = SyncOperationFactory.create()
        _op2 = SyncOperationFactory.create()
        _op3 = SyncOperationFactory.create()

        operations = list(SyncOperation.objects.all())

        # Most recent first
        assert operations[0].server_timestamp >= operations[1].server_timestamp
        assert operations[1].server_timestamp >= operations[2].server_timestamp


@pytest.mark.django_db
class TestFieldLevelLWWMixin:
    """Tests for FieldLevelLWWMixin functionality."""

    def test_get_field_timestamp_returns_none_for_unset(self, sync_registry, test_contact_factory):
        """Should return None for fields without timestamps."""
        org = OrganizationFactory.create()
        contact = test_contact_factory(organization=org, name="Test")

        # Clear timestamps for testing
        contact.field_timestamps = {}
        contact.save(update_fields=["field_timestamps"])

        result = contact.get_field_timestamp("name")

        assert result is None

    def test_set_field_timestamp_stores_iso_format(self, sync_registry, test_contact_factory):
        """Should store timestamps in ISO format."""
        org = OrganizationFactory.create()
        contact = test_contact_factory(organization=org, name="Test")

        timestamp = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        contact.set_field_timestamp("name", timestamp)

        assert contact.field_timestamps["name"] == "2025-01-23T10:30:00+00:00"

    def test_get_field_timestamp_parses_iso_format(self, sync_registry, test_contact_factory):
        """Should parse ISO timestamps back to datetime."""
        org = OrganizationFactory.create()
        contact = test_contact_factory(organization=org, name="Test")

        expected = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        contact.field_timestamps = {"name": "2025-01-23T10:30:00+00:00"}
        contact.save(update_fields=["field_timestamps"])

        result = contact.get_field_timestamp("name")

        assert result == expected

    def test_update_fields_with_timestamps(self, sync_registry, test_contact_factory):
        """Should update multiple fields and their timestamps."""
        org = OrganizationFactory.create()
        contact = test_contact_factory(organization=org, name="Original")

        timestamp = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        contact.update_fields_with_timestamps(
            {"name": "Updated", "phone": "555-1234"},
            timestamp,
        )

        assert contact.name == "Updated"
        assert contact.phone == "555-1234"
        assert contact.get_field_timestamp("name") == timestamp
        assert contact.get_field_timestamp("phone") == timestamp

    def test_get_syncable_fields_excludes_system_fields(self, sync_registry, test_contact_factory):
        """Should exclude system fields from syncable fields list."""
        from tests.sync.conftest import SyncTestContact

        fields = SyncTestContact.get_syncable_fields()

        # Should include data fields
        assert "name" in fields
        assert "email" in fields
        assert "phone" in fields

        # Should exclude system fields
        assert "id" not in fields
        assert "organization" not in fields
        assert "created_at" not in fields
        assert "updated_at" not in fields
        assert "deleted_at" not in fields
        assert "sync_version" not in fields
        assert "field_timestamps" not in fields

    def test_lww_excluded_fields_contains_expected(self):
        """Should have expected fields in LWW_EXCLUDED_FIELDS."""
        excluded = FieldLevelLWWMixin.LWW_EXCLUDED_FIELDS

        assert "id" in excluded
        assert "organization" in excluded
        assert "organization_id" in excluded
        assert "created_at" in excluded
        assert "updated_at" in excluded
        assert "deleted_at" in excluded
        assert "sync_version" in excluded
        assert "field_timestamps" in excluded
        assert "last_modified_by" in excluded
        assert "device_id" in excluded
