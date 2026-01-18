"""
Audit Lambda - EventBridge consumer for audit log creation.

This Lambda subscribes to audit-worthy domain events and creates
entries in the AuditLog table for compliance and debugging.

Features:
- Idempotent: Uses event_id with ON CONFLICT DO NOTHING
- Secure: Credentials from Secrets Manager, TLS to RDS Proxy
- Lean: ~100 lines, fast cold starts
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import psycopg2
from generated_schema import AUDIT_EVENT_TYPES, FIELDS, INSERT_SQL

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SYSTEM_ACTOR_ID = "system"


def get_db_credentials() -> dict[str, str]:
    """
    Fetch DB credentials from Secrets Manager (cached for Lambda warm starts).

    RDS secrets contain: host, port, dbname, username, password, engine.
    We use credentials but connect via RDS Proxy for connection pooling.
    """
    import boto3

    if not hasattr(get_db_credentials, "_cache"):
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=os.environ["DATABASE_SECRET_ARN"])
        get_db_credentials._cache = json.loads(response["SecretString"])
    return get_db_credentials._cache


def get_db_connection():
    """Get database connection via RDS Proxy with TLS."""
    creds = get_db_credentials()
    # Connect via RDS Proxy (from env) using Aurora credentials (from secret)
    return psycopg2.connect(
        host=os.environ.get("RDS_PROXY_HOST", creds["host"]),
        port=creds.get("port", "5432"),
        dbname=creds.get("dbname", "tango"),
        user=creds["username"],
        password=creds["password"],
        sslmode="require",
    )


def extract_field_value(field: str, detail: dict[str, Any]) -> Any:
    """Extract field value from EventBridge detail, mapping event structure to DB columns."""
    data = detail.get("data", {})
    actor = detail.get("actor", {})

    # Direct mappings from event envelope
    if field == "event_id":
        return detail.get("event_id")
    if field == "aggregate_type":
        return detail.get("aggregate_type")
    if field == "aggregate_id":
        return detail.get("aggregate_id")
    if field == "organization_id":
        return detail.get("organization_id")
    if field == "correlation_id":
        return detail.get("correlation_id")

    # Action = event_type
    if field == "action":
        return detail.get("event_type")

    # Actor fields
    if field == "actor_id":
        return actor.get("id") or SYSTEM_ACTOR_ID
    if field == "actor_email":
        return actor.get("email") or ""

    # Request context from data
    if field == "ip_address":
        return data.get("ip_address")
    if field == "user_agent":
        return data.get("user_agent", "")

    # Diff = remaining data (excluding ip_address, user_agent)
    if field == "diff":
        diff_data = dict(data)
        diff_data.pop("ip_address", None)
        diff_data.pop("user_agent", None)
        return json.dumps(diff_data)

    # Metadata (empty for event-derived audit logs)
    if field == "metadata":
        return json.dumps({})

    # Timestamp
    if field == "created_at":
        occurred_at = detail.get("occurred_at")
        if occurred_at:
            return occurred_at
        return datetime.now(UTC).isoformat()

    return None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """EventBridge event handler for audit log creation."""
    detail = event.get("detail", {})
    event_type = detail.get("event_type")
    event_id = detail.get("event_id")

    if event_type not in AUDIT_EVENT_TYPES:
        logger.info("Skipping non-audit event: %s", event_type)
        return {"status": "skipped", "reason": "not audit-worthy"}

    try:
        values = [extract_field_value(f, detail) for f in FIELDS]

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(INSERT_SQL, values)
            conn.commit()

        logger.info("Audit log created: event_id=%s, event_type=%s", event_id, event_type)
        return {"status": "created", "event_id": event_id}

    except Exception as e:
        logger.exception("Failed to create audit log: event_id=%s, error=%s", event_id, e)
        raise  # Re-raise to trigger DLQ
