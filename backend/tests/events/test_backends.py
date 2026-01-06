"""
Tests for event backends.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.events.backends import EventBridgeBackend, LocalBackend, get_backend
from apps.events.schemas import ActorSchema, EventEnvelope


def create_test_envelope(**kwargs) -> EventEnvelope:
    """Create a test event envelope with defaults."""
    defaults = {
        "event_id": uuid4(),
        "event_type": "test.event",
        "schema_version": 1,
        "occurred_at": datetime.now(UTC),
        "aggregate_id": "test_123",
        "aggregate_type": "test",
        "organization_id": "org_456",
        "correlation_id": uuid4(),
        "actor": ActorSchema(type="user", id="usr_789", email="test@example.com"),
        "data": {"key": "value"},
    }
    defaults.update(kwargs)
    return EventEnvelope(**defaults)


class TestLocalBackend:
    """Tests for LocalBackend."""

    def test_publish_returns_success_for_all_events(self):
        """Test LocalBackend returns success for all published events."""
        backend = LocalBackend()
        events = [create_test_envelope() for _ in range(3)]

        results = backend.publish(events)

        assert len(results) == 3
        for result in results:
            assert result["status"] == "success"
            assert "event_id" in result

    def test_publish_logs_event_details(self, caplog):
        """Test LocalBackend logs event details."""
        import logging

        caplog.set_level(logging.INFO)
        backend = LocalBackend()
        event = create_test_envelope(event_type="member.invited")

        backend.publish([event])

        assert "member.invited" in caplog.text
        assert "[LocalBackend]" in caplog.text

    def test_publish_empty_list(self):
        """Test publishing empty list returns empty results."""
        backend = LocalBackend()
        results = backend.publish([])
        assert results == []

    def test_publish_serializes_event_to_json(self):
        """Test LocalBackend serializes event to JSON (same as prod)."""
        backend = LocalBackend()
        event = create_test_envelope(data={"nested": {"deep": "value"}})

        # Should not raise - proves JSON serialization works
        results = backend.publish([event])
        assert len(results) == 1


class TestEventBridgeBackend:
    """Tests for EventBridgeBackend."""

    def test_publish_single_event(self):
        """Test publishing a single event to EventBridge."""
        from unittest.mock import MagicMock, patch

        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            import sys

            mock_boto3 = sys.modules["boto3"]
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.put_events.return_value = {"Entries": [{"EventId": "eb-123"}]}

            backend = EventBridgeBackend(event_bus_name="test-bus")
            backend._client = mock_client  # Inject mock directly
            event = create_test_envelope()

            results = backend.publish([event])

            mock_client.put_events.assert_called_once()
            call_args = mock_client.put_events.call_args[1]["Entries"]
            assert len(call_args) == 1
            assert call_args[0]["EventBusName"] == "test-bus"
            assert call_args[0]["DetailType"] == event.event_type

            assert results[0]["status"] == "success"
            assert results[0]["eventbridge_id"] == "eb-123"

    def test_publish_batches_events(self):
        """Test events are batched (max 10 per PutEvents call)."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        # Return appropriate number of entries for each batch (10, then 5)
        mock_client.put_events.side_effect = [
            {"Entries": [{"EventId": f"eb-{i}"} for i in range(10)]},
            {"Entries": [{"EventId": f"eb-{i}"} for i in range(10, 15)]},
        ]

        backend = EventBridgeBackend(event_bus_name="test-bus")
        backend._client = mock_client
        events = [create_test_envelope() for _ in range(15)]

        results = backend.publish(events)

        # Should make 2 calls: 10 + 5
        assert mock_client.put_events.call_count == 2
        assert len(results) == 15

    def test_publish_handles_per_entry_errors(self):
        """Test handling per-entry errors from EventBridge."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.put_events.return_value = {
            "Entries": [
                {"EventId": "eb-123"},
                {"ErrorCode": "ThrottlingException", "ErrorMessage": "Rate exceeded"},
            ]
        }

        backend = EventBridgeBackend(event_bus_name="test-bus")
        backend._client = mock_client
        events = [create_test_envelope() for _ in range(2)]

        results = backend.publish(events)

        assert results[0]["status"] == "success"
        assert results[1]["status"] == "error"
        assert "Rate exceeded" in results[1]["error"]

    def test_publish_handles_api_exception(self):
        """Test handling EventBridge API exceptions."""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.put_events.side_effect = Exception("Connection failed")

        backend = EventBridgeBackend(event_bus_name="test-bus")
        backend._client = mock_client
        events = [create_test_envelope() for _ in range(2)]

        results = backend.publish(events)

        assert len(results) == 2
        assert all(r["status"] == "error" for r in results)
        assert "Connection failed" in results[0]["error"]


class TestGetBackend:
    """Tests for get_backend factory function."""

    def test_get_backend_returns_local_by_default(self, settings):
        """Test default backend is LocalBackend."""
        settings.EVENT_BACKEND = "local"
        backend = get_backend()
        assert isinstance(backend, LocalBackend)

    def test_get_backend_returns_eventbridge(self, settings):
        """Test eventbridge backend is returned when configured."""
        settings.EVENT_BACKEND = "eventbridge"
        settings.EVENT_BUS_NAME = "my-bus"
        backend = get_backend()
        assert isinstance(backend, EventBridgeBackend)
        assert backend.event_bus_name == "my-bus"

    def test_get_backend_raises_if_missing_bus_name(self, settings):
        """Test error when eventbridge configured without bus name."""
        settings.EVENT_BACKEND = "eventbridge"
        settings.EVENT_BUS_NAME = ""
        with pytest.raises(ValueError, match="EVENT_BUS_NAME"):
            get_backend()
