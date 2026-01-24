"""
Tests for sync services.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.sync.models import SyncOperation
from apps.sync.schemas import SyncOperationIn
from apps.sync.services import (
    _serialize_entity,
    fetch_changes_for_pull,
    process_sync_operation,
    to_sync_result_out,
)
from tests.accounts.factories import MemberFactory, OrganizationFactory
from tests.sync.conftest import SyncTestContact


@pytest.mark.django_db
class TestProcessSyncOperation:
    """Tests for process_sync_operation function."""

    def test_create_operation_creates_entity(self, sync_registry, test_contact_factory):
        """Should create a new entity for create intent."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        operation = SyncOperationIn(
            idempotency_key="create_001",
            entity_type="test_contact",
            entity_id="tc_01HN8J1234567890ABCDEF01",
            intent="create",
            client_timestamp=timezone.now(),
            data={"name": "New Contact", "email": "new@example.com"},
        )

        result = process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )

        assert result.status == "applied"
        assert result.server_version == 1

        # Verify entity was created
        contact = SyncTestContact.objects.get(id="tc_01HN8J1234567890ABCDEF01")
        assert contact.name == "New Contact"
        assert contact.email == "new@example.com"

    def test_update_operation_updates_entity(self, sync_registry, test_contact_factory):
        """Should update existing entity for update intent."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        # Create existing entity
        contact = test_contact_factory(
            organization=org,
            name="Original",
            email="original@example.com",
        )

        operation = SyncOperationIn(
            idempotency_key="update_001",
            entity_type="test_contact",
            entity_id=contact.id,
            intent="update",
            client_timestamp=timezone.now(),
            data={"name": "Updated"},
        )

        result = process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )

        assert result.status == "applied"

        contact.refresh_from_db()
        assert contact.name == "Updated"
        assert contact.email == "original@example.com"  # Unchanged

    def test_delete_operation_soft_deletes_entity(self, sync_registry, test_contact_factory):
        """Should soft delete entity for delete intent."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        contact = test_contact_factory(organization=org, name="To Delete")

        operation = SyncOperationIn(
            idempotency_key="delete_001",
            entity_type="test_contact",
            entity_id=contact.id,
            intent="delete",
            client_timestamp=timezone.now(),
            data={},
        )

        result = process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )

        assert result.status == "applied"

        # Should be soft-deleted
        contact.refresh_from_db()
        assert contact.is_deleted

        # Should not appear in normal queries
        assert not SyncTestContact.objects.filter(id=contact.id).exists()

        # Should appear in all_objects
        assert SyncTestContact.all_objects.filter(id=contact.id).exists()

    def test_duplicate_idempotency_key_returns_duplicate(self, sync_registry, test_contact_factory):
        """Should return duplicate status for same idempotency key."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        operation = SyncOperationIn(
            idempotency_key="same_key",
            entity_type="test_contact",
            entity_id="tc_01HN8J1234567890ABCDEF01",
            intent="create",
            client_timestamp=timezone.now(),
            data={"name": "First"},
        )

        # First call succeeds
        result1 = process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )
        assert result1.status == "applied"

        # Second call with same key returns duplicate
        result2 = process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )
        assert result2.status == "duplicate"

    def test_unknown_entity_type_rejected(self, sync_registry):
        """Should reject operations for unknown entity types."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        operation = SyncOperationIn(
            idempotency_key="unknown_001",
            entity_type="nonexistent_type",
            entity_id="id_123",
            intent="create",
            client_timestamp=timezone.now(),
            data={"name": "Test"},
        )

        result = process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )

        assert result.status == "rejected"
        assert result.error_code == "UNKNOWN_ENTITY_TYPE"

    def test_update_nonexistent_entity_rejected(self, sync_registry):
        """Should reject updates for nonexistent entities."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        operation = SyncOperationIn(
            idempotency_key="update_missing",
            entity_type="test_contact",
            entity_id="tc_nonexistent",
            intent="update",
            client_timestamp=timezone.now(),
            data={"name": "Updated"},
        )

        result = process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )

        assert result.status == "rejected"
        assert result.error_code == "NOT_FOUND"

    def test_creates_sync_operation_record(self, sync_registry, test_contact_factory):
        """Should create SyncOperation record for audit."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        operation = SyncOperationIn(
            idempotency_key="audit_001",
            entity_type="test_contact",
            entity_id="tc_01HN8J1234567890ABCDEF01",
            intent="create",
            client_timestamp=timezone.now(),
            data={"name": "Audited"},
        )

        process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_xyz",
        )

        sync_op = SyncOperation.objects.get(idempotency_key="audit_001")
        assert sync_op.entity_type == "test_contact"
        assert sync_op.intent == "create"
        assert sync_op.device_id == "device_xyz"
        assert sync_op.status == SyncOperation.Status.APPLIED

    def test_drift_ms_calculated(self, sync_registry, test_contact_factory):
        """Should calculate drift between client and server timestamps."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        # Client timestamp 5 seconds ago
        client_ts = timezone.now() - timedelta(seconds=5)

        operation = SyncOperationIn(
            idempotency_key="drift_001",
            entity_type="test_contact",
            entity_id="tc_01HN8J1234567890ABCDEF01",
            intent="create",
            client_timestamp=client_ts,
            data={"name": "Test"},
        )

        process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )

        sync_op = SyncOperation.objects.get(idempotency_key="drift_001")
        assert sync_op.drift_ms is not None
        assert 4500 <= sync_op.drift_ms <= 6000  # ~5 seconds

    def test_idempotent_create_restores_deleted(self, sync_registry, test_contact_factory):
        """Should restore soft-deleted entity on create with same ID."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        # Create and delete
        contact = test_contact_factory(
            organization=org,
            name="Deleted",
            entity_id="tc_01HN8J1234567890RESTORE",
        )
        contact.soft_delete()
        assert contact.is_deleted

        # Create with same ID restores
        operation = SyncOperationIn(
            idempotency_key="restore_001",
            entity_type="test_contact",
            entity_id="tc_01HN8J1234567890RESTORE",
            intent="create",
            client_timestamp=timezone.now(),
            data={"name": "Restored"},
        )

        result = process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )

        assert result.status == "applied"

        contact.refresh_from_db()
        assert not contact.is_deleted
        assert contact.name == "Restored"

    def test_retry_count_stored(self, sync_registry, test_contact_factory):
        """Should store client retry count for observability."""
        org = OrganizationFactory.create()
        member = MemberFactory.create(organization=org)

        operation = SyncOperationIn(
            idempotency_key="retry_001",
            entity_type="test_contact",
            entity_id="tc_01HN8J1234567890ABCDEF01",
            intent="create",
            client_timestamp=timezone.now(),
            retry_count=3,
            data={"name": "Retried"},
        )

        process_sync_operation(
            organization=org,
            actor=member,
            operation=operation,
            device_id="device_123",
        )

        sync_op = SyncOperation.objects.get(idempotency_key="retry_001")
        assert sync_op.client_retry_count == 3


@pytest.mark.django_db
class TestFetchChangesForPull:
    """Tests for fetch_changes_for_pull function."""

    def test_returns_all_changes_without_cursor(self, sync_registry, test_contact_factory):
        """Should return all changes when no cursor provided."""
        org = OrganizationFactory.create()

        _c1 = test_contact_factory(organization=org, name="Contact 1")
        _c2 = test_contact_factory(organization=org, name="Contact 2")

        changes, cursor, has_more = fetch_changes_for_pull(
            organization=org,
            entity_types=None,
            since_cursor=None,
            limit=100,
        )

        assert len(changes) == 2
        assert cursor is not None
        assert not has_more

    def test_respects_limit(self, sync_registry, test_contact_factory):
        """Should respect the limit parameter."""
        org = OrganizationFactory.create()

        for i in range(5):
            test_contact_factory(organization=org, name=f"Contact {i}")

        changes, cursor, has_more = fetch_changes_for_pull(
            organization=org,
            entity_types=None,
            since_cursor=None,
            limit=3,
        )

        assert len(changes) == 3
        assert cursor is not None
        assert has_more

    def test_pagination_with_cursor(self, sync_registry, test_contact_factory):
        """Should paginate using cursor."""
        org = OrganizationFactory.create()

        for i in range(5):
            test_contact_factory(organization=org, name=f"Contact {i}")

        # First page
        changes1, cursor1, has_more1 = fetch_changes_for_pull(
            organization=org,
            entity_types=None,
            since_cursor=None,
            limit=3,
        )

        assert len(changes1) == 3
        assert has_more1

        # Second page
        changes2, cursor2, has_more2 = fetch_changes_for_pull(
            organization=org,
            entity_types=None,
            since_cursor=cursor1,
            limit=3,
        )

        assert len(changes2) == 2
        assert not has_more2

        # No overlap
        ids1 = {c.entity_id for c in changes1}
        ids2 = {c.entity_id for c in changes2}
        assert ids1.isdisjoint(ids2)

    def test_includes_deleted_records(self, sync_registry, test_contact_factory):
        """Should include soft-deleted records in pull."""
        org = OrganizationFactory.create()

        c1 = test_contact_factory(organization=org, name="Active")
        c2 = test_contact_factory(organization=org, name="Deleted")
        c2.soft_delete()

        changes, _, _ = fetch_changes_for_pull(
            organization=org,
            entity_types=None,
            since_cursor=None,
            limit=100,
        )

        assert len(changes) == 2

        operations = {c.entity_id: c.operation for c in changes}
        assert operations[c1.id] == "upsert"
        assert operations[c2.id] == "delete"

    def test_delete_operation_has_no_data(self, sync_registry, test_contact_factory):
        """Deleted records should have null data."""
        org = OrganizationFactory.create()

        contact = test_contact_factory(organization=org, name="Deleted")
        contact.soft_delete()

        changes, _, _ = fetch_changes_for_pull(
            organization=org,
            entity_types=None,
            since_cursor=None,
            limit=100,
        )

        assert len(changes) == 1
        assert changes[0].operation == "delete"
        assert changes[0].data is None

    def test_filters_by_entity_type(self, sync_registry, test_contact_factory):
        """Should filter by entity types when specified."""
        org = OrganizationFactory.create()

        test_contact_factory(organization=org, name="Contact")

        # Filter for a type that exists
        changes, _, _ = fetch_changes_for_pull(
            organization=org,
            entity_types=["test_contact"],
            since_cursor=None,
            limit=100,
        )

        assert len(changes) == 1

        # Filter for a type that doesn't exist
        changes2, _, _ = fetch_changes_for_pull(
            organization=org,
            entity_types=["nonexistent"],
            since_cursor=None,
            limit=100,
        )

        assert len(changes2) == 0

    def test_isolates_organizations(self, sync_registry, test_contact_factory):
        """Should only return changes for the specified organization."""
        org1 = OrganizationFactory.create()
        org2 = OrganizationFactory.create()

        test_contact_factory(organization=org1, name="Org1 Contact")
        test_contact_factory(organization=org2, name="Org2 Contact")

        changes, _, _ = fetch_changes_for_pull(
            organization=org1,
            entity_types=None,
            since_cursor=None,
            limit=100,
        )

        assert len(changes) == 1
        assert changes[0].data["name"] == "Org1 Contact"

    def test_ordered_by_updated_at(self, sync_registry, test_contact_factory):
        """Should return changes ordered by updated_at."""
        org = OrganizationFactory.create()

        c1 = test_contact_factory(organization=org, name="First")
        c2 = test_contact_factory(organization=org, name="Second")
        c3 = test_contact_factory(organization=org, name="Third")

        # Update c1 to make it most recent
        c1.name = "First Updated"
        c1.save()

        changes, _, _ = fetch_changes_for_pull(
            organization=org,
            entity_types=None,
            since_cursor=None,
            limit=100,
        )

        # c2, c3 (original order), then c1 (updated last)
        ids = [c.entity_id for c in changes]
        assert ids.index(c2.id) < ids.index(c3.id) < ids.index(c1.id)

    def test_upsert_includes_full_data(self, sync_registry, test_contact_factory):
        """Upsert operations should include full entity data."""
        org = OrganizationFactory.create()

        contact = test_contact_factory(
            organization=org,
            name="Full Data",
            email="full@example.com",
            phone="555-1234",
        )

        changes, _, _ = fetch_changes_for_pull(
            organization=org,
            entity_types=None,
            since_cursor=None,
            limit=100,
        )

        assert len(changes) == 1
        data = changes[0].data
        assert data["name"] == "Full Data"
        assert data["email"] == "full@example.com"
        assert data["phone"] == "555-1234"
        assert data["id"] == contact.id
        assert data["sync_version"] == contact.sync_version


@pytest.mark.django_db
class TestSerializeEntity:
    """Tests for _serialize_entity function."""

    def test_uses_custom_serializer_when_registered(self, sync_registry, test_contact_factory):
        """Should use custom serializer if registered."""
        org = OrganizationFactory.create()
        contact = test_contact_factory(organization=org, name="Custom")

        result = _serialize_entity("test_contact", contact)

        # Custom serializer includes field_timestamps
        assert "field_timestamps" in result

    def test_excludes_sensitive_fields(self, sync_registry, test_contact_factory):
        """Should exclude organization and other sensitive fields."""
        org = OrganizationFactory.create()
        contact = test_contact_factory(organization=org, name="Secure")

        result = _serialize_entity("test_contact", contact)

        assert "organization" not in result
        assert "organization_id" not in result
        assert "deleted_at" not in result


@pytest.mark.django_db
class TestToSyncResultOut:
    """Tests for to_sync_result_out helper."""

    def test_converts_sync_result_to_schema(self):
        """Should convert SyncResult to API schema."""
        from apps.sync.services import SyncResult

        result = SyncResult(
            status="applied",
            server_timestamp=timezone.now(),
            server_version=5,
        )

        out = to_sync_result_out(result, "key_123")

        assert out.idempotency_key == "key_123"
        assert out.status == "applied"
        assert out.server_version == 5

    def test_includes_error_info_for_rejected(self):
        """Should include error info for rejected operations."""
        from apps.sync.services import SyncResult

        result = SyncResult(
            status="rejected",
            server_timestamp=timezone.now(),
            error_code="VALIDATION_ERROR",
            error_message="Invalid email",
            error_details={"email": ["Invalid format"]},
        )

        out = to_sync_result_out(result, "key_456")

        assert out.status == "rejected"
        assert out.error_code == "VALIDATION_ERROR"
        assert out.error_message == "Invalid email"
        assert out.error_details == {"email": ["Invalid format"]}
