"""
Event backends - pluggable publishing backends.

LocalBackend: Logs events to console (dev)
EventBridgeBackend: Publishes to AWS EventBridge (production)
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from apps.events.schemas import EventEnvelope

logger = logging.getLogger(__name__)


class EventBackend(ABC):
    """Abstract base class for event publishing backends."""

    @abstractmethod
    def publish(self, events: list[EventEnvelope]) -> list[dict[str, Any]]:
        """
        Publish a batch of events.

        Returns list of results with status for each event:
        [{"event_id": "...", "status": "success"}, ...]
        """
        pass


class LocalBackend(EventBackend):
    """
    Local development backend.

    Logs events to console with the same serialization as production.
    Useful for development and testing without AWS.
    """

    def publish(self, events: list[EventEnvelope]) -> list[dict[str, Any]]:
        """Log events to console."""
        results = []

        for event in events:
            # Use same JSON serialization as EventBridge
            event_json = event.model_dump_json(indent=2)

            logger.info(
                "[LocalBackend] Event published:\n"
                "  Type: %s\n"
                "  Aggregate: %s/%s\n"
                "  Organization: %s\n"
                "  Payload:\n%s",
                event.event_type,
                event.aggregate_type,
                event.aggregate_id,
                event.organization_id,
                event_json,
            )

            results.append({"event_id": str(event.event_id), "status": "success"})

        return results


class EventBridgeBackend(EventBackend):
    """
    AWS EventBridge backend for production.

    Publishes events in batches (up to 10 per PutEvents call).
    """

    def __init__(self, event_bus_name: str, source: str = "app.events"):
        self.event_bus_name = event_bus_name
        self.source = source
        self._client = None

    @property
    def client(self):
        """Lazy-load boto3 client."""
        if self._client is None:
            import boto3

            self._client = boto3.client("events")
        return self._client

    def publish(self, events: list[EventEnvelope]) -> list[dict[str, Any]]:
        """Publish events to EventBridge in batches."""
        results = []

        # EventBridge PutEvents supports up to 10 entries per call
        batch_size = 10
        for i in range(0, len(events), batch_size):
            batch = events[i : i + batch_size]
            batch_results = self._publish_batch(batch)
            results.extend(batch_results)

        return results

    def _publish_batch(self, events: list[EventEnvelope]) -> list[dict[str, Any]]:
        """Publish a single batch of events."""
        entries = []
        for event in events:
            entries.append(
                {
                    "Source": self.source,
                    "DetailType": event.event_type,
                    "Detail": event.model_dump_json(),
                    "EventBusName": self.event_bus_name,
                }
            )

        try:
            response = self.client.put_events(Entries=entries)
        except Exception as e:
            logger.error("EventBridge PutEvents failed: %s", e)
            # Return all as failed
            return [
                {"event_id": str(event.event_id), "status": "error", "error": str(e)}
                for event in events
            ]

        # Process per-entry results
        results = []
        for idx, entry_result in enumerate(response.get("Entries", [])):
            event = events[idx]
            if entry_result.get("ErrorCode"):
                results.append(
                    {
                        "event_id": str(event.event_id),
                        "status": "error",
                        "error": entry_result.get("ErrorMessage", "Unknown error"),
                    }
                )
            else:
                results.append(
                    {
                        "event_id": str(event.event_id),
                        "status": "success",
                        "eventbridge_id": entry_result.get("EventId"),
                    }
                )

        return results


def get_backend() -> EventBackend:
    """
    Get the configured event backend.

    Uses EVENT_BACKEND setting: 'local' or 'eventbridge'
    """
    from django.conf import settings

    backend_type = getattr(settings, "EVENT_BACKEND", "local")

    if backend_type == "eventbridge":
        event_bus_name = getattr(settings, "EVENT_BUS_NAME", "")
        if not event_bus_name:
            raise ValueError("EVENT_BUS_NAME setting required for eventbridge backend")
        return EventBridgeBackend(event_bus_name=event_bus_name)

    return LocalBackend()
