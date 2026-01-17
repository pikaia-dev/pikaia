"""
Tests for event models.
"""

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.events.models import AuditLog, OutboxEvent


@pytest.mark.django_db
class TestOutboxEvent:
    """Tests for OutboxEvent model."""

    def test_create_outbox_event(self):
        """Test creating an outbox event with required fields."""
        event = OutboxEvent.objects.create(
            event_type="member.invited",
            aggregate_type="member",
            aggregate_id="mbr_123",
            organization_id="org_456",
            payload={
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "member.invited",
                "data": {"email": "test@example.com"},
            },
        )

        assert event.id is not None
        assert event.event_id is not None
        assert event.event_type == "member.invited"
        assert event.aggregate_type == "member"
        assert event.aggregate_id == "mbr_123"
        assert event.organization_id == "org_456"
        assert event.status == OutboxEvent.Status.PENDING
        assert event.attempts == 0
        assert event.published_at is None

    def test_mark_published(self):
        """Test marking an event as published."""
        event = OutboxEvent.objects.create(
            event_type="member.invited",
            aggregate_type="member",
            aggregate_id="mbr_123",
            organization_id="org_456",
            payload={"data": {}},
        )

        event.mark_published()
        event.refresh_from_db()

        assert event.status == OutboxEvent.Status.PUBLISHED
        assert event.published_at is not None

    def test_mark_failed_with_retry(self):
        """Test marking an event as failed schedules retry."""
        event = OutboxEvent.objects.create(
            event_type="member.invited",
            aggregate_type="member",
            aggregate_id="mbr_123",
            organization_id="org_456",
            payload={"data": {}},
        )

        event.mark_failed("Network error", max_attempts=10)
        event.refresh_from_db()

        assert event.status == OutboxEvent.Status.PENDING
        assert event.attempts == 1
        assert event.last_error == "Network error"
        assert event.next_attempt_at is not None
        assert event.next_attempt_at > timezone.now()

    def test_mark_failed_exceeds_max_attempts(self):
        """Test event marked as FAILED after max attempts."""
        event = OutboxEvent.objects.create(
            event_type="member.invited",
            aggregate_type="member",
            aggregate_id="mbr_123",
            organization_id="org_456",
            payload={"data": {}},
            attempts=9,  # Already tried 9 times
        )

        event.mark_failed("Network error", max_attempts=10)
        event.refresh_from_db()

        assert event.status == OutboxEvent.Status.FAILED
        assert event.attempts == 10
        assert event.next_attempt_at is None

    def test_event_id_is_unique(self):
        """Test event_id uniqueness constraint."""
        import uuid

        event_id = uuid.uuid4()

        OutboxEvent.objects.create(
            event_id=event_id,
            event_type="member.invited",
            aggregate_type="member",
            aggregate_id="mbr_123",
            organization_id="org_456",
            payload={"data": {}},
        )

        with pytest.raises(IntegrityError):
            OutboxEvent.objects.create(
                event_id=event_id,
                event_type="member.invited",
                aggregate_type="member",
                aggregate_id="mbr_456",
                organization_id="org_456",
                payload={"data": {}},
            )


@pytest.mark.django_db
class TestAuditLog:
    """Tests for AuditLog model."""

    def test_create_audit_log(self):
        """Test creating an audit log entry."""
        log = AuditLog.objects.create(
            action="member.role_changed",
            aggregate_type="member",
            aggregate_id="mbr_123",
            organization_id="org_456",
            actor_id="usr_789",
            actor_email="admin@example.com",
            diff={"old": {"role": "member"}, "new": {"role": "admin"}},
            ip_address="192.168.1.1",
        )

        assert log.id is not None
        assert log.action == "member.role_changed"
        assert log.actor_email == "admin@example.com"
        assert log.diff["old"]["role"] == "member"
        assert log.diff["new"]["role"] == "admin"
        assert log.ip_address == "192.168.1.1"
