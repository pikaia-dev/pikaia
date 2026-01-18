"""
Auto-generated audit schema from Django model.
DO NOT EDIT - run: uv run python manage.py generate_audit_schema
"""

TABLE_NAME = "events_auditlog"

FIELDS = [
    "event_id",
    "action",
    "aggregate_type",
    "aggregate_id",
    "organization_id",
    "actor_id",
    "actor_email",
    "correlation_id",
    "ip_address",
    "user_agent",
    "diff",
    "metadata",
    "created_at",
]

INSERT_SQL = """INSERT INTO events_auditlog (id, event_id, action, aggregate_type, aggregate_id, organization_id, actor_id, actor_email, correlation_id, ip_address, user_agent, diff, metadata, created_at)
VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (event_id) DO NOTHING"""

# Audit-worthy event types (single source of truth)
AUDIT_EVENT_TYPES = [
    "member.bulk_invited",
    "member.invited",
    "member.joined",
    "member.removed",
    "member.role_changed",
    "organization.billing_updated",
    "organization.created",
    "organization.updated",
    "user.phone_changed",
    "user.profile_updated",
]
