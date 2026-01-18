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
from apps.events.backends import LocalBackend, get_backend
from apps.events.management.commands.generate_audit_schema import AUDIT_EVENT_TYPES
from apps.events.models import AuditLog, OutboxEvent
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
            "event_publisher_started",
            backend=backend.__class__.__name__,
            batch_size=batch_size,
        )

        while not self._shutdown_requested:
            try:
                published_count = self._publish_batch(backend, batch_size, max_attempts)

                if published_count > 0:
                    logger.info("events_published", count=published_count)
                    # Continue immediately if we published events
                    continue

            except Exception:
                logger.exception("event_publisher_error")

            if once:
                break

            # No events or error - wait before next poll
            self._sleep_with_jitter(poll_interval)

        logger.info("event_publisher_shutdown")

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
                logger.error("event_payload_parse_failed", event_id=str(event.event_id), error=str(e))
                event.mark_failed(f"Payload parse error: {e}", max_attempts)
                continue

        if not envelopes:
            return 0

        # Publish batch
        results = backend.publish(envelopes)

        # Process results
        published_count = 0
        is_local_backend = isinstance(backend, LocalBackend)

        for event, result in zip(events, results, strict=True):
            if result.get("status") == "success":
                event.status = OutboxEvent.Status.PUBLISHED
                event.published_at = timezone.now()
                event.save(update_fields=["status", "published_at"])
                published_count += 1

                # Local dev fallback: create audit logs directly for LocalBackend
                if is_local_backend and event.event_type in AUDIT_EVENT_TYPES:
                    self._create_local_audit_log(event)
            else:
                error = result.get("error", "Unknown error")
                event.mark_failed(error, max_attempts)
                logger.warning("event_publish_failed", event_id=str(event.event_id), error=error)

        return published_count

    def _create_local_audit_log(self, event: OutboxEvent) -> None:
        """
        Create audit log entry for local development.

        In production, the Lambda consumer creates audit logs from EventBridge events.
        This fallback ensures local development still gets audit logs.
        """
        payload = event.payload
        data = dict(payload.get("data", {}))
        actor = payload.get("actor", {})

        # Extract request context from data
        ip_address = data.pop("ip_address", None)
        user_agent = data.pop("user_agent", "")

        # Use get_or_create for idempotency (event_id is unique)
        AuditLog.objects.get_or_create(
            event_id=event.event_id,
            defaults={
                "action": event.event_type,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": event.aggregate_id,
                "organization_id": event.organization_id,
                "actor_id": actor.get("id") or "system",
                "actor_email": actor.get("email") or "",
                "correlation_id": payload.get("correlation_id"),
                "ip_address": ip_address,
                "user_agent": user_agent,
                "diff": data,
            },
        )

    def _sleep_with_jitter(self, base_seconds: float) -> None:
        """Sleep with random jitter to avoid thundering herd."""
        jitter = base_seconds * 0.2 * random.random()
        time.sleep(base_seconds + jitter)

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on SIGINT/SIGTERM."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_signal)

    def _handle_signal(self, signum, frame) -> None:
        logger.info("event_publisher_signal_received", signal=signum)
        self._shutdown_requested = True
