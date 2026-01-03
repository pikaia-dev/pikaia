"""
Tests for EventEnvelope schema.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from apps.events.schemas import ActorSchema, EventEnvelope, MAX_PAYLOAD_SIZE_BYTES


class TestActorSchema:
    """Tests for ActorSchema."""

    def test_user_actor(self):
        """Test creating a user actor."""
        actor = ActorSchema(type="user", id="usr_123", email="test@example.com")
        assert actor.type == "user"
        assert actor.id == "usr_123"
        assert actor.email == "test@example.com"

    def test_system_actor(self):
        """Test creating a system actor."""
        actor = ActorSchema(type="system", id="system")
        assert actor.type == "system"
        assert actor.email is None

    def test_actor_requires_type_and_id(self):
        """Test actor requires type and id fields."""
        with pytest.raises(ValidationError):
            ActorSchema(type="user")  # Missing id


class TestEventEnvelope:
    """Tests for EventEnvelope schema."""

    def test_create_valid_envelope(self):
        """Test creating a valid event envelope."""
        envelope = EventEnvelope(
            event_id=uuid4(),
            event_type="member.invited",
            occurred_at=datetime.now(timezone.utc),
            aggregate_id="mbr_123",
            aggregate_type="member",
            organization_id="org_456",
            actor=ActorSchema(type="user", id="usr_789"),
            data={"email": "test@example.com"},
        )

        assert envelope.event_type == "member.invited"
        assert envelope.schema_version == 1  # Default
        assert envelope.data["email"] == "test@example.com"

    def test_envelope_requires_core_fields(self):
        """Test envelope requires all core fields."""
        with pytest.raises(ValidationError):
            EventEnvelope(
                event_type="test.event",
                # Missing required fields
            )

    def test_envelope_serializes_to_json(self):
        """Test envelope serializes correctly to JSON."""
        event_id = uuid4()
        correlation_id = uuid4()
        occurred_at = datetime.now(timezone.utc)

        envelope = EventEnvelope(
            event_id=event_id,
            event_type="test.event",
            occurred_at=occurred_at,
            aggregate_id="test_123",
            aggregate_type="test",
            organization_id="org_456",
            correlation_id=correlation_id,
            actor=ActorSchema(type="system", id="system"),
            data={"nested": {"key": "value"}},
        )

        # Serialize to dict then JSON string
        data = envelope.model_dump(mode="json")

        # UUIDs should be strings
        assert data["event_id"] == str(event_id)
        assert data["correlation_id"] == str(correlation_id)

        # Datetime should be ISO format
        assert isinstance(data["occurred_at"], str)

        # Data should be preserved
        assert data["data"]["nested"]["key"] == "value"

    def test_envelope_with_optional_fields(self):
        """Test envelope handles optional fields correctly."""
        envelope = EventEnvelope(
            event_id=uuid4(),
            event_type="test.event",
            occurred_at=datetime.now(timezone.utc),
            aggregate_id="test_123",
            aggregate_type="test",
            organization_id="org_456",
            actor=ActorSchema(type="system", id="system"),
            # correlation_id is optional
        )

        assert envelope.correlation_id is None
        assert envelope.data == {}  # Default empty dict

    def test_envelope_data_can_contain_complex_types(self):
        """Test data field supports complex nested structures."""
        envelope = EventEnvelope(
            event_id=uuid4(),
            event_type="test.event",
            occurred_at=datetime.now(timezone.utc),
            aggregate_id="test_123",
            aggregate_type="test",
            organization_id="org_456",
            actor=ActorSchema(type="system", id="system"),
            data={
                "string": "value",
                "number": 42,
                "float": 3.14,
                "boolean": True,
                "null": None,
                "array": [1, 2, 3],
                "nested": {"deep": {"deeper": "value"}},
            },
        )

        data = envelope.model_dump(mode="json")["data"]
        assert data["string"] == "value"
        assert data["number"] == 42
        assert data["array"] == [1, 2, 3]
        assert data["nested"]["deep"]["deeper"] == "value"


class TestPayloadSizeLimit:
    """Tests for payload size validation."""

    def test_max_payload_size_is_256kb(self):
        """Test MAX_PAYLOAD_SIZE_BYTES is 256KB."""
        assert MAX_PAYLOAD_SIZE_BYTES == 256 * 1024

    def test_envelope_json_size_can_be_calculated(self):
        """Test we can calculate envelope JSON size."""
        envelope = EventEnvelope(
            event_id=uuid4(),
            event_type="test.event",
            occurred_at=datetime.now(timezone.utc),
            aggregate_id="test_123",
            aggregate_type="test",
            organization_id="org_456",
            actor=ActorSchema(type="system", id="system"),
        )

        json_str = envelope.model_dump_json()
        size_bytes = len(json_str.encode("utf-8"))

        # Basic envelope should be well under 256KB
        assert size_bytes < MAX_PAYLOAD_SIZE_BYTES
        assert size_bytes < 1024  # Should be under 1KB
