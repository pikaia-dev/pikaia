"""
Tests for sync API endpoints.
"""

from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.core.auth import AuthContext
from apps.sync.api import sync_pull, sync_push
from apps.sync.models import SyncOperation
from apps.sync.schemas import SyncOperationIn, SyncPullParams, SyncPushRequest
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory
from tests.conftest import make_request_with_auth


@pytest.mark.django_db
class TestSyncPushEndpoint:
    """Tests for POST /sync/push endpoint."""

    def test_push_single_create_operation(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should create entity and return applied status."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                SyncOperationIn(
                    idempotency_key="push_create_001",
                    entity_type="test_contact",
                    entity_id="tc_01HN8J1234567890ABCDEF01",
                    intent="create",
                    client_timestamp=timezone.now(),
                    data={"name": "New Contact", "email": "new@example.com"},
                )
            ],
        )

        with patch("apps.sync.api.publish_event"):
            response = sync_push(request, payload)

        assert len(response.results) == 1
        assert response.results[0].status == "applied"
        assert response.results[0].idempotency_key == "push_create_001"

    def test_push_batch_operations(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should process multiple operations in a batch."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                SyncOperationIn(
                    idempotency_key="batch_001",
                    entity_type="test_contact",
                    entity_id="tc_batch_01",
                    intent="create",
                    client_timestamp=timezone.now(),
                    data={"name": "Contact 1"},
                ),
                SyncOperationIn(
                    idempotency_key="batch_002",
                    entity_type="test_contact",
                    entity_id="tc_batch_02",
                    intent="create",
                    client_timestamp=timezone.now(),
                    data={"name": "Contact 2"},
                ),
            ],
        )

        with patch("apps.sync.api.publish_event"):
            response = sync_push(request, payload)

        assert len(response.results) == 2
        assert all(r.status == "applied" for r in response.results)

    def test_push_update_operation(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should update existing entity."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        contact = test_contact_factory(
            organization=org, name="Original", email="original@example.com"
        )

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                SyncOperationIn(
                    idempotency_key="push_update_001",
                    entity_type="test_contact",
                    entity_id=contact.id,
                    intent="update",
                    client_timestamp=timezone.now(),
                    data={"name": "Updated"},
                )
            ],
        )

        with patch("apps.sync.api.publish_event"):
            response = sync_push(request, payload)

        assert response.results[0].status == "applied"

        contact.refresh_from_db()
        assert contact.name == "Updated"
        assert contact.email == "original@example.com"

    def test_push_delete_operation(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should soft delete entity."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        contact = test_contact_factory(organization=org, name="To Delete")

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                SyncOperationIn(
                    idempotency_key="push_delete_001",
                    entity_type="test_contact",
                    entity_id=contact.id,
                    intent="delete",
                    client_timestamp=timezone.now(),
                    data={},
                )
            ],
        )

        response = sync_push(request, payload)

        assert response.results[0].status == "applied"

        contact.refresh_from_db()
        assert contact.is_deleted

    def test_push_duplicate_idempotency_key(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should return duplicate for repeated idempotency key."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        operation = SyncOperationIn(
            idempotency_key="duplicate_key",
            entity_type="test_contact",
            entity_id="tc_duplicate",
            intent="create",
            client_timestamp=timezone.now(),
            data={"name": "Test"},
        )

        # First push
        payload1 = SyncPushRequest(device_id="device_001", operations=[operation])
        with patch("apps.sync.api.publish_event"):
            response1 = sync_push(request, payload1)
        assert response1.results[0].status == "applied"

        # Second push with same key
        payload2 = SyncPushRequest(device_id="device_001", operations=[operation])
        response2 = sync_push(request, payload2)
        assert response2.results[0].status == "duplicate"

    def test_push_unknown_entity_type_rejected(
        self, request_factory: RequestFactory, sync_registry
    ):
        """Should reject unknown entity types."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                SyncOperationIn(
                    idempotency_key="unknown_type",
                    entity_type="nonexistent",
                    entity_id="id_123",
                    intent="create",
                    client_timestamp=timezone.now(),
                    data={"name": "Test"},
                )
            ],
        )

        response = sync_push(request, payload)

        assert response.results[0].status == "rejected"
        assert response.results[0].error_code == "UNKNOWN_ENTITY_TYPE"

    def test_push_batch_max_limit(self, request_factory: RequestFactory, sync_registry, settings):
        """Should reject batches exceeding max size."""
        from ninja.errors import HttpError

        settings.SYNC_PUSH_MAX_BATCH_SIZE = 5

        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        operations = [
            SyncOperationIn(
                idempotency_key=f"batch_{i}",
                entity_type="test_contact",
                entity_id=f"tc_{i}",
                intent="create",
                client_timestamp=timezone.now(),
                data={"name": f"Contact {i}"},
            )
            for i in range(10)  # Exceeds limit of 5
        ]

        payload = SyncPushRequest(device_id="device_001", operations=operations)

        with pytest.raises(HttpError) as exc_info:
            sync_push(request, payload)

        assert exc_info.value.status_code == 400
        assert "Maximum" in str(exc_info.value.message)

    def test_push_creates_sync_operation_records(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should create SyncOperation records for auditing."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        payload = SyncPushRequest(
            device_id="device_audit",
            operations=[
                SyncOperationIn(
                    idempotency_key="audit_key",
                    entity_type="test_contact",
                    entity_id="tc_audit",
                    intent="create",
                    client_timestamp=timezone.now(),
                    data={"name": "Audited"},
                )
            ],
        )

        with patch("apps.sync.api.publish_event"):
            sync_push(request, payload)

        sync_op = SyncOperation.objects.get(idempotency_key="audit_key")
        assert sync_op.device_id == "device_audit"
        assert sync_op.status == SyncOperation.Status.APPLIED

    def test_push_partial_success(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should report individual results for batch with mixed success."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                # This should succeed
                SyncOperationIn(
                    idempotency_key="success_001",
                    entity_type="test_contact",
                    entity_id="tc_success",
                    intent="create",
                    client_timestamp=timezone.now(),
                    data={"name": "Success"},
                ),
                # This should fail (update nonexistent)
                SyncOperationIn(
                    idempotency_key="fail_001",
                    entity_type="test_contact",
                    entity_id="tc_nonexistent",
                    intent="update",
                    client_timestamp=timezone.now(),
                    data={"name": "Fail"},
                ),
            ],
        )

        with patch("apps.sync.api.publish_event"):
            response = sync_push(request, payload)

        assert len(response.results) == 2
        assert response.results[0].status == "applied"
        assert response.results[1].status == "rejected"


@pytest.mark.django_db
class TestSyncPullEndpoint:
    """Tests for GET /sync/pull endpoint."""

    def test_pull_returns_all_changes(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should return all changes without cursor."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        test_contact_factory(organization=org, name="Contact 1")
        test_contact_factory(organization=org, name="Contact 2")

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        params = SyncPullParams()
        response = sync_pull(request, params)

        assert len(response.changes) == 2
        assert response.cursor is not None
        assert not response.has_more

    def test_pull_with_cursor_pagination(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should paginate with cursor."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        for i in range(5):
            test_contact_factory(organization=org, name=f"Contact {i}")

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        # First page
        params1 = SyncPullParams(limit=3)
        response1 = sync_pull(request, params1)

        assert len(response1.changes) == 3
        assert response1.has_more
        assert response1.cursor is not None

        # Second page
        params2 = SyncPullParams(since=response1.cursor, limit=3)
        response2 = sync_pull(request, params2)

        assert len(response2.changes) == 2
        assert not response2.has_more

    def test_pull_includes_deleted(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should include soft-deleted records as delete operations."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        contact = test_contact_factory(organization=org, name="Deleted")
        contact.soft_delete()

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        params = SyncPullParams()
        response = sync_pull(request, params)

        assert len(response.changes) == 1
        assert response.changes[0].operation == "delete"
        assert response.changes[0].data is None

    def test_pull_filters_by_entity_type(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should filter by entity types."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        test_contact_factory(organization=org, name="Contact")

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        # Filter for existing type
        params = SyncPullParams(entity_types="test_contact")
        response = sync_pull(request, params)
        assert len(response.changes) == 1

        # Filter for non-existing type
        params2 = SyncPullParams(entity_types="nonexistent")
        response2 = sync_pull(request, params2)
        assert len(response2.changes) == 0

    def test_pull_isolates_organizations(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should only return changes for requesting organization."""
        org1 = OrganizationFactory.create()
        org2 = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org1)

        test_contact_factory(organization=org1, name="Org1")
        test_contact_factory(organization=org2, name="Org2")

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org1)
        )

        params = SyncPullParams()
        response = sync_pull(request, params)

        assert len(response.changes) == 1
        assert response.changes[0].data["name"] == "Org1"

    def test_pull_invalid_cursor_returns_400(self, request_factory: RequestFactory, sync_registry):
        """Should return 400 for invalid cursor."""
        from ninja.errors import HttpError

        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        params = SyncPullParams(since="invalid-cursor")

        with pytest.raises(HttpError) as exc_info:
            sync_pull(request, params)

        assert exc_info.value.status_code == 400

    def test_pull_respects_max_limit(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory, settings
    ):
        """Should cap limit at max limit setting."""
        settings.SYNC_PULL_MAX_LIMIT = 10

        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        for i in range(15):
            test_contact_factory(organization=org, name=f"Contact {i}")

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        # Request more than max
        params = SyncPullParams(limit=500)
        response = sync_pull(request, params)

        # Should be capped at max
        assert len(response.changes) == 10

    def test_pull_change_includes_version(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should include sync_version in changes."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        contact = test_contact_factory(organization=org, name="Test")

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        params = SyncPullParams()
        response = sync_pull(request, params)

        assert len(response.changes) == 1
        assert response.changes[0].version == contact.sync_version

    def test_pull_returns_updated_at(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should include updated_at timestamp in changes."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        contact = test_contact_factory(organization=org, name="Test")

        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        params = SyncPullParams()
        response = sync_pull(request, params)

        assert response.changes[0].updated_at is not None
        # Updated at should match contact's
        assert abs((response.changes[0].updated_at - contact.updated_at).total_seconds()) < 1

    def test_pull_empty_returns_same_cursor(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Should return input cursor when no new changes."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        _contact = test_contact_factory(organization=org, name="Test")

        # Get initial cursor
        request = request_factory.get("/api/v1/sync/pull")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        params1 = SyncPullParams()
        response1 = sync_pull(request, params1)
        initial_cursor = response1.cursor

        # Pull again with same cursor (no new changes)
        params2 = SyncPullParams(since=initial_cursor)
        response2 = sync_pull(request, params2)

        assert len(response2.changes) == 0
        assert response2.cursor == initial_cursor


@pytest.mark.django_db
class TestSyncRoundTrip:
    """End-to-end sync tests combining push and pull."""

    def test_create_then_pull(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Created entity should appear in next pull."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        # Push create
        push_payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                SyncOperationIn(
                    idempotency_key="roundtrip_create",
                    entity_type="test_contact",
                    entity_id="tc_roundtrip",
                    intent="create",
                    client_timestamp=timezone.now(),
                    data={"name": "Roundtrip Contact"},
                )
            ],
        )

        with patch("apps.sync.api.publish_event"):
            push_response = sync_push(request, push_payload)

        assert push_response.results[0].status == "applied"

        # Pull
        pull_params = SyncPullParams()
        pull_response = sync_pull(request, pull_params)

        assert len(pull_response.changes) == 1
        assert pull_response.changes[0].entity_id == "tc_roundtrip"
        assert pull_response.changes[0].operation == "upsert"

    def test_update_then_pull(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Updated entity should reflect changes in next pull."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        contact = test_contact_factory(organization=org, name="Original")

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        # Push update
        push_payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                SyncOperationIn(
                    idempotency_key="roundtrip_update",
                    entity_type="test_contact",
                    entity_id=contact.id,
                    intent="update",
                    client_timestamp=timezone.now(),
                    data={"name": "Updated Name"},
                )
            ],
        )

        with patch("apps.sync.api.publish_event"):
            push_response = sync_push(request, push_payload)

        assert push_response.results[0].status == "applied"

        # Pull
        pull_params = SyncPullParams()
        pull_response = sync_pull(request, pull_params)

        assert len(pull_response.changes) == 1
        assert pull_response.changes[0].data["name"] == "Updated Name"

    def test_delete_then_pull(
        self, request_factory: RequestFactory, sync_registry, test_contact_factory
    ):
        """Deleted entity should appear as delete operation in pull."""
        org = OrganizationFactory.create()
        user = UserFactory.create()
        member = MemberFactory.create(user=user, organization=org)

        contact = test_contact_factory(organization=org, name="To Delete")

        request = request_factory.post("/api/v1/sync/push")
        request = make_request_with_auth(
            request, AuthContext(user=user, member=member, organization=org)
        )

        # Push delete
        push_payload = SyncPushRequest(
            device_id="device_001",
            operations=[
                SyncOperationIn(
                    idempotency_key="roundtrip_delete",
                    entity_type="test_contact",
                    entity_id=contact.id,
                    intent="delete",
                    client_timestamp=timezone.now(),
                    data={},
                )
            ],
        )

        push_response = sync_push(request, push_payload)
        assert push_response.results[0].status == "applied"

        # Pull
        pull_params = SyncPullParams()
        pull_response = sync_pull(request, pull_params)

        assert len(pull_response.changes) == 1
        assert pull_response.changes[0].entity_id == contact.id
        assert pull_response.changes[0].operation == "delete"
        assert pull_response.changes[0].data is None
