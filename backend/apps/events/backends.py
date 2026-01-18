"""
Event backends - pluggable publishing backends.

LocalBackend: Logs events to console (dev)
EventBridgeBackend: Publishes to AWS EventBridge (production)
"""

from abc import ABC, abstractmethod
from typing import Any

from apps.core.logging import get_logger
from apps.events.schemas import EventEnvelope

logger = get_logger(__name__)


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
            logger.info(
                "domain_event_published",
                event_type=event.event_type,
                event_id=str(event.event_id),
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                organization_id=event.organization_id,
                backend="local",
            )

            results.append({"event_id": str(event.event_id), "status": "success"})

        return results


class EventBridgeBackend(EventBackend):
    """
    AWS EventBridge backend for production.

    Publishes events in batches (up to 10 per PutEvents call).
    """

    # Timeout configuration for EventBridge API calls
    CONNECT_TIMEOUT = 5  # seconds to establish connection
    READ_TIMEOUT = 30  # seconds to wait for response

    def __init__(
        self, event_bus_name: str, source: str = "app.events", endpoint_url: str | None = None
    ):
        self.event_bus_name = event_bus_name
        self.source = source
        self.endpoint_url = endpoint_url
        self._client = None

    @property
    def client(self):
        """Lazy-load boto3 client with timeout configuration."""
        if self._client is None:
            import boto3
            from botocore.config import Config

            config = Config(
                connect_timeout=self.CONNECT_TIMEOUT,
                read_timeout=self.READ_TIMEOUT,
                retries={"max_attempts": 2},
            )
            # Build client kwargs - supports LocalStack via endpoint_url
            client_kwargs: dict[str, str | Config | None] = {
                "config": config,
                "endpoint_url": self.endpoint_url,
            }
            # Remove None values to let boto3 use defaults
            client_kwargs = {k: v for k, v in client_kwargs.items() if v is not None}

            self._client = boto3.client("events", **client_kwargs)  # type: ignore[arg-type]
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
            logger.error("eventbridge_put_events_failed", error=str(e), batch_size=len(events))
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
        endpoint_url = getattr(settings, "AWS_EVENTS_ENDPOINT_URL", None)
        return EventBridgeBackend(event_bus_name=event_bus_name, endpoint_url=endpoint_url)

    return LocalBackend()
