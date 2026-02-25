"""
Standalone Lambda handler for the event publisher.

This is a lightweight publisher that doesn't require Django.
It queries the outbox table directly and publishes to EventBridge.

Triggered by:
- Aurora PostgreSQL trigger on INSERT to outbox table (production)
- CloudWatch scheduled event (fallback polling)
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "10"))

# Events stuck in 'publishing' for longer than this are considered abandoned
# and will be reset to 'pending' for retry.
PUBLISHING_TIMEOUT_MINUTES = 5


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda entry point for event publishing.

    Triggered by Aurora PostgreSQL trigger when events are inserted,
    or by CloudWatch Events as a fallback polling mechanism.
    """
    if not DATABASE_URL:
        logger.error("DATABASE_URL not configured")
        return {"statusCode": 500, "body": "DATABASE_URL not configured"}

    try:
        published_count = publish_pending_events()
        return {"statusCode": 200, "body": f"Published {published_count} events"}
    except Exception as e:
        logger.exception("Failed to publish events: %s", e)
        return {"statusCode": 500, "body": str(e)}


def publish_pending_events() -> int:
    """
    Fetch pending events and publish to EventBridge.

    Uses a two-phase approach to minimize lock duration:
    1. SELECT FOR UPDATE SKIP LOCKED, mark as 'publishing', COMMIT (releases locks)
    2. Publish to EventBridge (no DB locks held)
    3. Update final status (published/failed)

    Also recovers events stuck in 'publishing' from crashed invocations.

    Returns number of successfully published events.
    """
    eventbridge = boto3.client("events")

    # Phase 1: Claim events (short transaction, releases locks quickly)
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Best-effort recovery of events stuck in 'publishing' from crashed
            # Lambda invocations.  Wrapped in try/except so a failure here
            # never blocks the main publish path.
            try:
                cur.execute(
                    """
                    UPDATE events_outboxevent
                    SET status = 'pending', claimed_at = NULL
                    WHERE status = 'publishing'
                      AND claimed_at IS NOT NULL
                      AND claimed_at < NOW() - %s * INTERVAL '1 minute'
                    """,
                    (PUBLISHING_TIMEOUT_MINUTES,),
                )
                recovered = cur.rowcount
                if recovered:
                    logger.info("Recovered %d stuck publishing events", recovered)
            except Exception:
                logger.exception("Stuck-event recovery failed, continuing with publish")
                conn.rollback()

            # Fetch and lock pending events
            cur.execute(
                """
                SELECT id, event_type, payload
                FROM events_outboxevent
                WHERE status = 'pending'
                  AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
                ORDER BY created_at
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (BATCH_SIZE,),
            )
            events = cur.fetchall()

            if not events:
                conn.commit()
                logger.info("No pending events to publish")
                return 0

            # Pre-parse payloads to catch JSON errors before claiming
            valid_events = []
            failed_events: list[tuple[Any, str]] = []

            for event in events:
                payload = event["payload"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON payload: {e}"
                        failed_events.append((event["id"], error_msg))
                        logger.warning(
                            "Failed to parse JSON for event %s: %s",
                            event["id"],
                            error_msg,
                        )
                        continue
                event["decoded_payload"] = payload
                valid_events.append(event)

            # Mark JSON failures immediately
            if failed_events:
                _mark_failed_events(cur, failed_events)

            if not valid_events:
                conn.commit()
                logger.info("No valid events to publish after JSON parsing")
                return 0

            # Mark valid events as 'publishing' to claim them.
            # claimed_at tracks when the row was claimed, separately from
            # next_attempt_at which preserves its backoff-scheduling semantics.
            # RETURNING id gives us only the rows we actually claimed, so we
            # don't publish events that were concurrently claimed by another
            # invocation.
            valid_ids = [e["id"] for e in valid_events]
            cur.execute(
                """
                UPDATE events_outboxevent
                SET status = 'publishing', claimed_at = NOW()
                WHERE id = ANY(%s)
                  AND status = 'pending'
                RETURNING id
                """,
                (valid_ids,),
            )
            claimed_ids = {row[0] for row in cur.fetchall()}
            valid_events = [e for e in valid_events if e["id"] in claimed_ids]

            if not valid_events:
                conn.commit()
                logger.info("No events claimed after concurrent filtering")
                return 0

        conn.commit()  # Releases all row locks

    # Phase 2: Publish to EventBridge (no DB locks held)
    logger.info("Publishing %d events", len(valid_events))
    published_ids = []
    publish_failures: list[tuple[Any, str]] = []

    for batch_start in range(0, len(valid_events), 10):
        batch = valid_events[batch_start : batch_start + 10]
        entries = []

        for event in batch:
            entries.append(
                {
                    "Source": "app.outbox",
                    "DetailType": event["event_type"],
                    "Detail": json.dumps(event["decoded_payload"]),
                    "EventBusName": EVENT_BUS_NAME,
                }
            )

        try:
            response = eventbridge.put_events(Entries=entries)

            for i, result in enumerate(response.get("Entries", [])):
                event_row = batch[i]
                if "EventId" in result:
                    published_ids.append(event_row["id"])
                else:
                    error = result.get("ErrorMessage", "Unknown error")
                    publish_failures.append((event_row["id"], error))
                    logger.warning(
                        "Failed to publish event %s: %s",
                        event_row["id"],
                        error,
                    )

        except Exception as e:
            logger.error("Batch publish failed: %s", e)
            for event_row in batch:
                publish_failures.append((event_row["id"], str(e)))

    # Phase 3: Update final status
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            if published_ids:
                cur.execute(
                    """
                    UPDATE events_outboxevent
                    SET status = 'published', published_at = %s, claimed_at = NULL
                    WHERE id = ANY(%s)
                    """,
                    (datetime.now(UTC), published_ids),
                )

            if publish_failures:
                _mark_failed_events(cur, publish_failures)

        conn.commit()

    logger.info(
        "Published %d events, %d failed",
        len(published_ids),
        len(publish_failures),
    )
    return len(published_ids)


def _mark_failed_events(cur: Any, failed_events: list[tuple[Any, str]]) -> None:
    """Mark failed events for retry with exponential backoff."""
    for event_id, error in failed_events:
        cur.execute(
            """
            UPDATE events_outboxevent
            SET
                attempts = attempts + 1,
                last_error = %s,
                next_attempt_at = NOW() + (INTERVAL '1 minute' * POWER(2, attempts)),
                claimed_at = NULL,
                status = CASE
                    WHEN attempts + 1 >= %s THEN 'failed'
                    ELSE 'pending'
                END
            WHERE id = %s
            """,
            (error, MAX_ATTEMPTS, event_id),
        )
