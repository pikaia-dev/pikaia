"""
Publish events management command.

Polls the outbox table and publishes pending events to the configured backend.
Uses SELECT FOR UPDATE SKIP LOCKED for safe concurrent execution.
"""

import random
import signal
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.logging import get_logger
from apps.events.backends import get_backend
from apps.events.models import OutboxEvent
from apps.events.schemas import EventEnvelope

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Publish pending events from the outbox to the event backend"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown_requested = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run once and exit (default: run continuously)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of events to process per batch (default: 100)",
        )
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=5.0,
            help="Seconds between polls when no events (default: 5)",
        )
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=10,
            help="Max publish attempts before marking as failed (default: 10)",
        )

    def handle(self, *args, **options):
        self._setup_signal_handlers()

        once = options["once"]
        batch_size = options["batch_size"]
        poll_interval = options["poll_interval"]
        max_attempts = options["max_attempts"]

        backend = get_backend()
        logger.info(
            "Starting event publisher (backend=%s, batch_size=%d)",
            backend.__class__.__name__,
            batch_size,
        )

        while not self._shutdown_requested:
            try:
                published_count = self._publish_batch(backend, batch_size, max_attempts)

                if published_count > 0:
                    logger.info("Published %d events", published_count)
                    # Continue immediately if we published events
                    continue

            except Exception as e:
                logger.exception("Error in publish loop: %s", e)

            if once:
                break

            # No events or error - wait before next poll
            self._sleep_with_jitter(poll_interval)

        logger.info("Event publisher shutting down")

    def _publish_batch(self, backend, batch_size: int, max_attempts: int) -> int:
        """
        Fetch and publish a batch of pending events.

        Uses SELECT FOR UPDATE SKIP LOCKED to allow concurrent workers.
        Returns number of events processed.
        """
        from django.db.models import Q

        now = timezone.now()

        with transaction.atomic():
            # Find pending events ready to publish
            # Either: never attempted (next_attempt_at is null) OR retry time has passed
            # SKIP LOCKED allows multiple workers to process different events
            events = list(
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(status=OutboxEvent.Status.PENDING)
                .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
                .order_by("created_at")[:batch_size]
            )

            if not events:
                return 0

        # Convert to EventEnvelope for publishing
        envelopes = []
        for event in events:
            try:
                envelope = EventEnvelope(**event.payload)
                envelopes.append(envelope)
            except Exception as e:
                logger.error("Failed to parse event %s payload: %s", event.event_id, e)
                event.mark_failed(f"Payload parse error: {e}", max_attempts)
                continue

        if not envelopes:
            return 0

        # Publish batch
        results = backend.publish(envelopes)

        # Process results
        published_count = 0
        for event, result in zip(events, results):
            if result.get("status") == "success":
                event.status = OutboxEvent.Status.PUBLISHED
                event.published_at = timezone.now()
                event.save(update_fields=["status", "published_at"])
                published_count += 1
            else:
                error = result.get("error", "Unknown error")
                event.mark_failed(error, max_attempts)
                logger.warning("Failed to publish event %s: %s", event.event_id, error)

        return published_count

    def _sleep_with_jitter(self, base_seconds: float) -> None:
        """Sleep with random jitter to avoid thundering herd."""
        jitter = base_seconds * 0.2 * random.random()
        time.sleep(base_seconds + jitter)

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on SIGINT/SIGTERM."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_signal)

    def _handle_signal(self, signum, frame) -> None:
        logger.info("Received signal %s, requesting shutdown", signum)
        self._shutdown_requested = True
