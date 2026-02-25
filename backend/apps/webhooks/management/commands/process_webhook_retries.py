"""
Process pending webhook delivery retries.

Finds WebhookDelivery records with status='pending' and next_retry_at <= now(),
then dispatches them using the existing WebhookDispatcher. Designed to be run
via cron or as a periodic task.

Usage:
    python manage.py process_webhook_retries --once          # single pass
    python manage.py process_webhook_retries                 # continuous polling
    python manage.py process_webhook_retries --batch-size 50 # custom batch size
"""

import random
import signal
import time
from datetime import timedelta
from uuid import UUID

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.logging import get_logger
from apps.events.models import OutboxEvent
from apps.webhooks.models import WebhookDelivery
from apps.webhooks.services import WebhookDispatcher, _record_delivery_result

logger = get_logger(__name__)

# Sentinel offset added to next_retry_at to claim deliveries within the
# SELECT FOR UPDATE transaction.  Other workers' `next_retry_at__lte=now`
# filter will skip these rows once the transaction commits and the lock is
# released.  If dispatch fails, `_record_delivery_result` overwrites
# next_retry_at with the real back-off value.
_CLAIM_OFFSET = timedelta(hours=1)


class Command(BaseCommand):
    help = "Process pending webhook delivery retries"

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
            help="Number of deliveries to process per batch (default: 100)",
        )
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=10.0,
            help="Seconds between polls when no deliveries found (default: 10)",
        )

    def handle(self, *args, **options):
        self._setup_signal_handlers()

        once = options["once"]
        batch_size = options["batch_size"]
        poll_interval = options["poll_interval"]

        logger.info(
            "webhook_retry_processor_started",
            batch_size=batch_size,
        )

        while not self._shutdown_requested:
            try:
                processed_count = self._process_batch(batch_size)

                if processed_count > 0:
                    self.stdout.write(f"Processed {processed_count} webhook retries")
                    logger.info("webhook_retries_processed", count=processed_count)
                    continue

            except Exception:
                logger.exception("webhook_retry_processor_error")

            if once:
                break

            self._sleep_with_jitter(poll_interval)

        logger.info("webhook_retry_processor_shutdown")

    def _process_batch(self, batch_size: int) -> int:
        """
        Fetch and process a batch of pending webhook deliveries due for retry.

        Uses SELECT FOR UPDATE SKIP LOCKED for safe concurrent execution.
        Deliveries are "claimed" inside the transaction by pushing their
        next_retry_at into the future so that other workers' filters skip
        them once locks are released.
        Returns number of deliveries processed.
        """
        now = timezone.now()

        with transaction.atomic():
            deliveries = list(
                WebhookDelivery.objects.select_for_update(skip_locked=True)
                .filter(
                    status=WebhookDelivery.Status.PENDING,
                    next_retry_at__lte=now,
                )
                .select_related("endpoint")
                .order_by("next_retry_at")[:batch_size]
            )

            if not deliveries:
                return 0

            # Claim: push next_retry_at into the future so concurrent workers
            # (whose filter uses next_retry_at__lte=now) will not pick these
            # rows up after the lock is released.
            claimed_ids = [d.id for d in deliveries]
            WebhookDelivery.objects.filter(id__in=claimed_ids).update(
                next_retry_at=now + _CLAIM_OFFSET,
            )

        dispatcher = WebhookDispatcher()
        processed = 0

        for delivery in deliveries:
            endpoint = delivery.endpoint

            if not endpoint.active:
                logger.info(
                    "skipping_retry_inactive_endpoint",
                    delivery_id=delivery.id,
                    endpoint_id=endpoint.id,
                )
                continue

            # Recover the original event payload from the outbox.
            # WebhookDelivery intentionally does not store payload (PII concerns),
            # so we look it up from the OutboxEvent that originated the delivery.
            # If the outbox event has been cleaned up or the event_id format does
            # not match, we fall back to an empty payload -- the webhook still
            # carries id, type, timestamp, and organization_id.
            event_data: dict = {}
            try:
                outbox_event = OutboxEvent.objects.get(event_id=UUID(delivery.event_id))
                event_data = outbox_event.payload.get("data", {})
            except (OutboxEvent.DoesNotExist, ValueError):
                logger.warning(
                    "outbox_event_not_found_for_retry",
                    delivery_id=delivery.id,
                    event_id=delivery.event_id,
                )

            result = dispatcher.dispatch(
                endpoint=endpoint,
                event_id=delivery.event_id,
                event_type=delivery.event_type,
                event_data=event_data,
                organization_id=str(endpoint.organization_id),
            )

            _record_delivery_result(delivery, result)
            processed += 1

            logger.info(
                "webhook_retry_dispatched",
                delivery_id=delivery.id,
                endpoint_id=endpoint.id,
                success=result.success,
                attempt=delivery.attempt_number,
            )

        return processed

    def _sleep_with_jitter(self, base_seconds: float) -> None:
        """Sleep with random jitter to avoid thundering herd."""
        jitter = base_seconds * 0.2 * random.random()
        time.sleep(base_seconds + jitter)

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown on SIGINT/SIGTERM."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_signal)

    def _handle_signal(self, signum, frame) -> None:
        logger.info("webhook_retry_processor_signal_received", signal=signum)
        self._shutdown_requested = True
