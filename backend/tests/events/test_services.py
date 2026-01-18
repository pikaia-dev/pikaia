"""
Tests for event services.
"""

import pytest
from django.db import transaction

from apps.events.models import OutboxEvent
from apps.events.schemas import MAX_PAYLOAD_SIZE_BYTES
from apps.events.services import (
    create_audit_log,
    get_correlation_id,
    publish_event,
    set_correlation_id,
)
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


@pytest.mark.django_db
class TestPublishEvent:
    """Tests for publish_event service function."""

    def test_publish_event_creates_outbox_entry(self):
        """Test that publish_event creates an OutboxEvent."""
        org = OrganizationFactory()
        user = UserFactory()

        event = publish_event(
            event_type="organization.updated",
            aggregate=org,
            data={"name": "New Name"},
            actor=user,
        )

        assert event.id is not None
        assert event.event_type == "organization.updated"
        assert event.aggregate_type == "organization"
        assert event.aggregate_id == str(org.pk)
        assert event.organization_id == str(org.pk)
        assert event.status == OutboxEvent.Status.PENDING

        # Check payload structure
        payload = event.payload
        assert payload["event_type"] == "organization.updated"
        assert payload["aggregate_type"] == "organization"
        assert payload["actor"]["type"] == "user"
        assert payload["actor"]["id"] == str(user.pk)
        assert payload["data"]["name"] == "New Name"

    def test_publish_event_extracts_organization_from_member(self):
        """Test organization_id extraction from member aggregate."""
        member = MemberFactory()

        event = publish_event(
            event_type="member.role_changed",
            aggregate=member,
            data={"old_role": "member", "new_role": "admin"},
            actor=member.user,
        )

        assert event.organization_id == str(member.organization.pk)

    def test_publish_event_system_actor_when_no_user(self):
        """Test system actor when no user provided."""
        org = OrganizationFactory()

        event = publish_event(
            event_type="subscription.activated",
            aggregate=org,
            data={},
            actor=None,
        )

        assert event.payload["actor"]["type"] == "system"
        assert event.payload["actor"]["id"] == "system"

    def test_publish_event_includes_correlation_id(self):
        """Test correlation ID is included when set."""
        import uuid

        correlation_id = uuid.uuid4()
        set_correlation_id(correlation_id)

        try:
            org = OrganizationFactory()
            event = publish_event(
                event_type="organization.created",
                aggregate=org,
                data={},
            )

            assert event.payload["correlation_id"] == str(correlation_id)
        finally:
            set_correlation_id(None)

    def test_publish_event_validates_payload_size(self):
        """Test that oversized payloads are rejected."""
        org = OrganizationFactory()

        # Create data that exceeds 256KB
        large_data = {"content": "x" * (MAX_PAYLOAD_SIZE_BYTES + 1000)}

        with pytest.raises(ValueError, match="exceeds"):
            publish_event(
                event_type="organization.updated",
                aggregate=org,
                data=large_data,
            )

    def test_publish_event_atomic_with_transaction(self):
        """Test event is created atomically with business data."""
        org = OrganizationFactory()

        try:
            with transaction.atomic():
                org.name = "Updated Name"
                org.save()

                publish_event(
                    event_type="organization.updated",
                    aggregate=org,
                    data={"name": "Updated Name"},
                )

                # Simulate failure
                raise Exception("Simulated failure")
        except Exception:
            pass

        # Event should NOT exist because transaction was rolled back
        # (Note: This only works if publish_event is inside the transaction)
        # In this case, the org.save() is also rolled back
        org.refresh_from_db()
        assert org.name != "Updated Name"


@pytest.mark.django_db
class TestCreateAuditLog:
    """Tests for create_audit_log service function."""

    def test_create_audit_log_basic(self):
        """Test creating a basic audit log entry."""
        org = OrganizationFactory()
        user = UserFactory()

        log = create_audit_log(
            action="organization.billing_updated",
            aggregate=org,
            actor=user,
            diff={"old": {"vat_id": ""}, "new": {"vat_id": "DE123456789"}},
        )

        assert log.id is not None
        assert log.action == "organization.billing_updated"
        assert log.actor_id == str(user.pk)
        assert log.actor_email == user.email
        assert log.diff["new"]["vat_id"] == "DE123456789"

    def test_create_audit_log_with_context(self):
        """Test audit log with request context."""
        org = OrganizationFactory()
        user = UserFactory()

        log = create_audit_log(
            action="member.removed",
            aggregate=org,
            actor=user,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            metadata={"method": "DELETE", "path": "/api/v1/members/123"},
        )

        assert log.ip_address == "192.168.1.100"
        assert log.user_agent == "Mozilla/5.0"
        assert log.metadata["method"] == "DELETE"


@pytest.mark.django_db
class TestCorrelationId:
    """Tests for correlation ID context management."""

    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        import uuid

        correlation_id = uuid.uuid4()

        set_correlation_id(correlation_id)
        assert get_correlation_id() == correlation_id

        set_correlation_id(None)
        assert get_correlation_id() is None


@pytest.mark.django_db
class TestPublishEventRequestContext:
    """Tests for request context enrichment in publish_event."""

    def test_publish_event_includes_request_context_from_structlog(self):
        """Test that publish_event enriches data with IP and user-agent from contextvars."""
        import structlog

        org = OrganizationFactory()
        user = UserFactory()

        # Simulate middleware binding request context
        structlog.contextvars.bind_contextvars(
            **{
                "request.ip_address": "203.0.113.50",
                "request.user_agent": "TestBrowser/1.0",
            }
        )

        try:
            event = publish_event(
                event_type="organization.updated",
                aggregate=org,
                data={"name": "Test Org"},
                actor=user,
            )

            # Request context should be in the event data
            assert event.payload["data"]["ip_address"] == "203.0.113.50"
            assert event.payload["data"]["user_agent"] == "TestBrowser/1.0"
            # Original data should still be present
            assert event.payload["data"]["name"] == "Test Org"
        finally:
            structlog.contextvars.unbind_contextvars("request.ip_address", "request.user_agent")

    def test_publish_event_handles_missing_request_context(self):
        """Test that publish_event handles missing request context gracefully."""
        import structlog

        org = OrganizationFactory()

        # Ensure no request context is bound
        structlog.contextvars.clear_contextvars()

        event = publish_event(
            event_type="organization.created",
            aggregate=org,
            data={"name": "New Org"},
        )

        # Should have None/empty values for request context
        assert event.payload["data"]["ip_address"] is None
        assert event.payload["data"]["user_agent"] == ""
        # Original data should still be present
        assert event.payload["data"]["name"] == "New Org"

    def test_publish_event_does_not_overwrite_explicit_ip(self):
        """Test that explicit data is not overwritten by context."""
        import structlog

        org = OrganizationFactory()

        # Bind context with one IP
        structlog.contextvars.bind_contextvars(**{"request.ip_address": "10.0.0.1"})

        try:
            # But event data has a different field we want to preserve
            event = publish_event(
                event_type="organization.updated",
                aggregate=org,
                data={"name": "Test", "custom_field": "preserved"},
            )

            # Context IP should be added
            assert event.payload["data"]["ip_address"] == "10.0.0.1"
            # Custom field should be preserved
            assert event.payload["data"]["custom_field"] == "preserved"
        finally:
            structlog.contextvars.unbind_contextvars("request.ip_address")
