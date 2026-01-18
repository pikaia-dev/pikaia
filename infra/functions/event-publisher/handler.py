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
from datetime import datetime, timezone

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


def handler(event: dict, context) -> dict:
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

    Uses FOR UPDATE SKIP LOCKED for safe concurrent execution:
    - Row locks prevent duplicate publishes from concurrent Lambdas
    - SKIP LOCKED allows other Lambdas to process different events
    - Lock held during EventBridge call (~100-500ms) is acceptable

    Returns number of successfully published events.
    """
    eventbridge = boto3.client("events")

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
                logger.info("No pending events to publish")
                return 0

            logger.info("Publishing %d events", len(events))

            # Publish to EventBridge (max 10 per PutEvents call)
            published_ids = []
            failed_events = []

            for batch_start in range(0, len(events), 10):
                batch = events[batch_start : batch_start + 10]
                entries = []

                for event in batch:
                    payload = event["payload"]
                    if isinstance(payload, str):
                        payload = json.loads(payload)

                    entries.append(
                        {
                            "Source": "app.outbox",
                            "DetailType": event["event_type"],
                            "Detail": json.dumps(payload),
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
                            failed_events.append((event_row["id"], error))
                            logger.warning(
                                "Failed to publish event %s: %s",
                                event_row["id"],
                                error,
                            )

                except Exception as e:
                    logger.error("Batch publish failed: %s", e)
                    for event_row in batch:
                        failed_events.append((event_row["id"], str(e)))

            # Mark successful events as published
            if published_ids:
                cur.execute(
                    """
                    UPDATE events_outboxevent
                    SET status = 'published', published_at = %s
                    WHERE id = ANY(%s)
                    """,
                    (datetime.now(timezone.utc), published_ids),
                )

            # Mark failed events for retry (with exponential backoff)
            for event_id, error in failed_events:
                cur.execute(
                    """
                    UPDATE events_outboxevent
                    SET
                        attempts = attempts + 1,
                        last_error = %s,
                        next_attempt_at = NOW() + (INTERVAL '1 minute' * POWER(2, attempts)),
                        status = CASE
                            WHEN attempts + 1 >= %s THEN 'failed'
                            ELSE 'pending'
                        END
                    WHERE id = %s
                    """,
                    (error, MAX_ATTEMPTS, event_id),
                )

            conn.commit()

            logger.info(
                "Published %d events, %d failed",
                len(published_ids),
                len(failed_events),
            )
            return len(published_ids)
