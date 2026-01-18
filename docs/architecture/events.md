# Event Architecture

This document defines the event-driven architecture for the bootstrap, covering event design, naming, schema versioning, and EventBridge usage patterns.

## Table of Contents

- [Overview](#overview)
- [Event Model](#event-model)
- [Naming Conventions](#naming-conventions)
- [Schema Versioning](#schema-versioning)
- [Internal vs Public Events](#internal-vs-public-events)
- [EventBridge Patterns](#eventbridge-patterns)
- [Audit Logging](#audit-logging)

---

## Overview

Events are the backbone of cross-service communication, integrations, and async workflows. The bootstrap uses **AWS EventBridge** as the central event bus with PostgreSQL as the source of truth.

### Core Principles

| Principle | Implementation |
|-----------|----------------|
| Events are facts, not commands | Past tense, immutable, append-only |
| Idempotency everywhere | Consumers handle duplicates gracefully |
| Schema evolution without breaking | Additive-only changes, version field |
| Debug-friendly | Correlation IDs, structured payloads |

### Event Flow Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Django    │─────▶│ EventBridge │─────▶│  Consumers  │
│   Service   │      │   (Bus)     │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
       │                    │                    │
       │                    ├──▶ Integration Router (webhooks)
       │                    ├──▶ Notification Lambda
       ▼                    ├──▶ Analytics Pipeline
┌─────────────┐             └──▶ Audit Log Writer
│ PostgreSQL  │
│ (source of  │
│   truth)    │
└─────────────┘
```

---

## Event Model

### Required Fields

Every event **must** include these fields:

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `event_id` | UUID | Unique identity for idempotency | `"550e8400-e29b-41d4-a716-446655440000"` |
| `event_type` | string | Semantic event name | `"member.invited"` |
| `schema_version` | integer | Payload version | `1` |
| `occurred_at` | ISO 8601 | When the event happened (business time) | `"2025-01-02T23:00:00Z"` |
| `aggregate_id` | string | Entity identity | `"123"` |
| `aggregate_type` | string | Entity type | `"member"` |
| `correlation_id` | UUID | Request trace ID | `"req_01HN8J..."` |
| `actor` | object | Who caused the event | `{"type": "user", "id": "42"}` |
| `organization_id` | string | Organization/tenant ID | `"1"` |

### Optional Fields

| Field | Type | Purpose |
|-------|------|---------|
| `causation_id` | UUID | ID of the event that caused this one |
| `producer` | string | Service that emitted the event |
| `metadata` | object | Additional context (IP, user-agent, etc.) |

### Event Envelope

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "member.invited",
  "schema_version": 1,
  "occurred_at": "2025-01-02T23:00:00Z",
  "aggregate_id": "123",
  "aggregate_type": "member",
  "organization_id": "1",
  "correlation_id": "req_01HN8J9K2M3N4P5Q6R7S8T9U0V",
  "actor": {
    "type": "user",
    "id": "42",
    "email": "admin@example.com"
  },
  "data": {
    "email": "newuser@example.com",
    "role": "member",
    "invited_by_member_id": "45"
  }
}
```

---

## Implemented Events

The following events are currently integrated into the codebase:

### Tier 1: Core Business Events

| Event Type | Aggregate | Trigger Location |
|------------|-----------|------------------|
| `organization.created` | Organization | `accounts/api.py` - create_organization |
| `member.invited` | Member | `accounts/api.py` - invite_member_endpoint |
| `member.joined` | Member | `accounts/api.py` - exchange_session |
| `member.removed` | Member | `accounts/api.py` + `accounts/webhooks.py` |

### Tier 2: Billing Events

| Event Type | Aggregate | Trigger Location |
|------------|-----------|------------------|
| `subscription.activated` | Subscription | `billing/services.py` - handle_subscription_created |
| `subscription.updated` | Subscription | `billing/services.py` - handle_subscription_updated |
| `subscription.canceled` | Subscription | `billing/services.py` - handle_subscription_deleted |

### Tier 3: Security/Audit Events

| Event Type | Aggregate | Trigger Location |
|------------|-----------|------------------|
| `member.role_changed` | Member | `accounts/api.py` - update_member_role_endpoint |
| `user.phone_changed` | User | `accounts/api.py` - verify_phone_otp |
| `organization.billing_updated` | Organization | `accounts/api.py` - update_billing |

---

## Naming Conventions

### Rules

1. **Past tense** — Events represent facts that happened
2. **Namespaced** — `{aggregate}.{action}` or `{aggregate}.{attribute}_changed`
3. **Business-meaningful** — Understandable without reading payload

### Good Examples

| Event Type | When to Use |
|------------|-------------|
| `time_entry.created` | New time entry recorded |
| `time_entry.submitted` | Entry submitted for approval |
| `time_entry.approved` | Manager approved the entry |
| `time_entry.rejected` | Manager rejected the entry |
| `user.phone_number_changed` | Specific field changed (security-relevant) |
| `workspace.member_invited` | New invite sent |
| `subscription.activated` | Billing subscription became active |

### Anti-Patterns

| ❌ Bad | ✅ Better | Why |
|--------|-----------|-----|
| `time_entry.changed` | `time_entry.description_updated` | Ambiguous, forces payload inspection |
| `update_time_entry` | `time_entry.updated` | Command, not event |
| `TIME_ENTRY_CREATED` | `time_entry.created` | Inconsistent casing |
| `db.write` | `time_entry.created` | Implementation detail, not business event |

### Event Categories

| Category | Pattern | Use Case |
|----------|---------|----------|
| **Lifecycle** | `{entity}.created`, `.deleted` | Entity creation/removal |
| **State Transition** | `{entity}.submitted`, `.approved` | Workflow state changes |
| **Attribute Change** | `{entity}.{field}_changed` | Security/audit-relevant field changes |
| **Sync/Replication** | `{entity}.upserted` | Offline sync, data distribution |

---

## Schema Versioning

### Strategy

- **Additive-only** — Never remove or rename fields
- **Version per event type** — `schema_version` in every event
- **Explicit consumer branching** — Consumers switch on version

### Breaking vs Non-Breaking Changes

| Change Type | Breaking? | Action |
|-------------|-----------|--------|
| Add optional field | No | No version bump needed |
| Add required field with default | No | No version bump needed |
| Remove field | **Yes** | Bump version, support old version |
| Rename field | **Yes** | Bump version, support old version |
| Change field type | **Yes** | Bump version, support old version |

### Handling Breaking Changes

```python
# Consumer code handling multiple versions
def handle_time_entry_created(event: dict):
    version = event["schema_version"]

    if version == 1:
        # Original format
        project_id = event["data"]["project_id"]
    elif version == 2:
        # Breaking change: project_id moved to nested object
        project_id = event["data"]["project"]["id"]
    else:
        raise UnsupportedSchemaVersion(version)
```

### Documentation

Event schemas are documented in `/docs/events/` with one file per event type:

```
docs/events/
├── time_entry.created.md
├── time_entry.submitted.md
├── user.phone_number_changed.md
└── ...
```

Each file contains:
- Overview and purpose
- Schema versions with field tables
- Breaking changes log
- Example payloads

---

## Internal vs Public Events

### Internal Events

- High volume, implementation details allowed
- May contain sensitive data
- Schema can evolve faster

### Public Events

- Explicit allow-list (curated subset of internal events)
- Stable contracts for external integrations
- Prefixed with `public.`
- Minimal, clean payloads

| Aspect | Internal | Public |
|--------|----------|--------|
| Naming | `time_entry.created` | `public.time_entry.created` |
| Audience | Internal services | Webhooks, Zapier, external |
| Payload | Rich, may include internals | Curated, stable |
| Versioning | Can evolve faster | Strict backward compatibility |

### Public Event Envelope

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "public.time_entry.created",
  "schema_version": 1,
  "occurred_at": "2025-01-02T23:00:00Z",
  "workspace_id": "org_01HN8J9K2M3N4P5Q6R7S8T9U0V",
  "data": {
    "id": "te_01HN8J9K2M3N4P5Q6R7S8T9U0V",
    "description": "Working on feature X",
    "project_id": "prj_01HN...",
    "duration_minutes": 45,
    "created_at": "2025-01-02T23:00:00Z"
  }
}
```

---

## EventBridge Patterns

### Custom Event Bus

Create a dedicated event bus per application (not per customer):

```python
# CDK example
from aws_cdk import aws_events as events

event_bus = events.EventBus(
    self, "AppEventBus",
    event_bus_name="timetracking-events"
)
```

### Publishing Events

```python
import boto3
import json
from datetime import datetime

eventbridge = boto3.client("events")

def publish_event(event: dict):
    """Publish event to EventBridge."""
    eventbridge.put_events(
        Entries=[{
            "Source": "timetracking.api",
            "DetailType": event["event_type"],
            "Detail": json.dumps(event),
            "EventBusName": "timetracking-events",
        }]
    )
```

### Event Rules (Limited Set)

Create a small, fixed set of rules—not per customer:

| Rule | Pattern | Target |
|------|---------|--------|
| Integration-eligible | `{"detail-type": [{"prefix": "public."}]}` | Integration Router SQS |
| Billing events | `{"detail-type": [{"prefix": "subscription."}]}` | Billing Lambda |
| Notification events | `{"detail-type": [{"suffix": ".created"}, {"suffix": ".approved"}]}` | Notification SQS |

### Dead Letter Queue (DLQ)

Always configure DLQs for failed deliveries:

```python
from aws_cdk import aws_sqs as sqs

dlq = sqs.Queue(
    self, "EventDLQ",
    queue_name="timetracking-events-dlq",
    retention_period=Duration.days(14)
)
```

---

## Audit Logging

### Audit Log vs Domain Event

A single action produces both:

| Aspect | Domain Event | Audit Log |
|--------|--------------|-----------|
| Purpose | Drive workflows, integrations | Compliance, security |
| Storage | EventBridge (transient) | PostgreSQL (permanent) |
| Payload | Minimal, business data | Rich: diffs, IP, user-agent |
| Retention | EventBridge default (24h) | Years |
| Access | Internal services | Support, compliance team |

### Audit Log Model

```python
class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    workspace_id = models.ForeignKey(Organization, on_delete=models.CASCADE)

    # What happened
    action = models.CharField(max_length=100)  # e.g., "user.phone_number_changed"
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=100)

    # Who did it
    actor_id = models.CharField(max_length=100)
    actor_email = models.EmailField()

    # Context
    correlation_id = models.UUIDField()
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)

    # Changes
    diff = models.JSONField(default=dict)  # {"old": {...}, "new": {...}}
    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace_id", "created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor_id"]),
        ]
```

### Example: Phone Number Change

**Domain Event** (for workflows):
```json
{
  "event_type": "user.phone_number_changed",
  "data": {
    "user_id": "usr_01HN...",
    "verified": false
  }
}
```

**Audit Log Entry** (for compliance):
```json
{
  "action": "user.phone_number_changed",
  "entity_type": "user",
  "entity_id": "usr_01HN...",
  "actor_email": "user@example.com",
  "ip_address": "192.168.1.1",
  "diff": {
    "old": {"phone": "+1***4567"},
    "new": {"phone": "+1***8901"}
  }
}
```

---

## Transactional Outbox

> [!IMPORTANT]
> The transactional outbox pattern is **required** for guaranteed event delivery. Events are persisted atomically with business data, then published by a background worker.

### Why Outbox?

Without outbox:
```python
# ❌ Dangerous: EventBridge call can fail after DB commit
with transaction.atomic():
    entry.status = "approved"
    entry.save()
eventbridge.put_events(...)  # Network failure = lost event
```

With outbox:
```python
# ✅ Safe: Event persisted in same transaction
with transaction.atomic():
    entry.status = "approved"
    entry.save()
    OutboxEvent.objects.create(event_type="time_entry.approved", ...)

# Background worker publishes, retries on failure
```

### Outbox Model

```python
class OutboxEvent(models.Model):
    """
    Transactional outbox for guaranteed event delivery.
    """
    class Status(models.TextChoices):
        PENDING = "pending"
        PUBLISHED = "published"
        FAILED = "failed"

    # Primary key - BigAutoField for B-tree locality on write-heavy table
    id = models.BigAutoField(primary_key=True)

    # Idempotency key - consumers use this to dedupe
    event_id = models.UUIDField(unique=True, default=uuid.uuid4, db_index=True)

    # Event identity
    event_type = models.CharField(max_length=100, db_index=True)
    aggregate_type = models.CharField(max_length=50)
    aggregate_id = models.CharField(max_length=100)
    organization_id = models.CharField(max_length=100, db_index=True)
    schema_version = models.PositiveIntegerField(default=1)

    # Full event payload (JSON)
    payload = models.JSONField()

    # Publishing lifecycle
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Retry tracking
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "next_attempt_at"]),  # Publisher query
        ]
```

### Publisher Worker

```python
def publish_pending_events():
    """
    Idempotent publisher - safe to run concurrently.
    Run via cron (every 5s) or triggered by transaction.on_commit().
    """
    pending = OutboxEvent.objects.filter(
        published_at__isnull=True,
        publish_attempts__lt=5,
    ).select_for_update(skip_locked=True)[:100]

    for event in pending:
        try:
            eventbridge.put_events(Entries=[{
                "Source": "app.outbox",
                "DetailType": event.event_type,
                "Detail": json.dumps(event.payload),
                "EventBusName": settings.EVENT_BUS_NAME,
            }])
            event.published_at = timezone.now()
        except Exception as e:
            event.publish_attempts += 1
            event.last_error = str(e)
        event.save()
```

### Alternative: Debezium + EventBridge Pipes

For higher throughput, use CDC (Change Data Capture):

```
PostgreSQL → Debezium → Kafka/Kinesis → EventBridge Pipes → EventBridge
```

This eliminates polling and provides sub-second latency.

### Publisher Deployment

The publisher can be triggered in multiple ways depending on environment:

#### Local Development

Run the management command manually or on a schedule:

```bash
# One-shot (useful for testing)
python manage.py publish_events --once

# Continuous polling (5s interval)
python manage.py publish_events --poll-interval=5
```

#### Production: Aurora Trigger → Lambda

For sub-second event delivery, use Aurora PostgreSQL triggers to invoke Lambda directly on INSERT:

```
┌─────────────────────────────────────────────────────────────┐
│ INSERT INTO events_outboxevent                              │
│         ↓                                                   │
│ Aurora PostgreSQL Trigger                                   │
│         ↓                                                   │
│ aws_lambda.invoke('publish-events-lambda')                  │
│         ↓                                                   │
│ Lambda runs: publish_events --once                          │
│         ↓                                                   │
│ Events published to EventBridge                             │
└─────────────────────────────────────────────────────────────┘
```

**Aurora Trigger Setup (SQL):**

```sql
-- Enable aws_lambda extension
CREATE EXTENSION IF NOT EXISTS aws_lambda CASCADE;

-- Grant Lambda invoke permission (via IAM role attached to Aurora)
-- Create trigger function
CREATE OR REPLACE FUNCTION notify_event_published()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM aws_lambda.invoke(
        aws_commons.create_lambda_function_arn(
            'publish-events-lambda',
            'us-east-1'  -- your region
        ),
        '{"source": "aurora-trigger"}'::json,
        'Event'  -- async invocation
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to outbox table
CREATE TRIGGER outbox_insert_trigger
AFTER INSERT ON events_outboxevent
FOR EACH STATEMENT  -- Per-statement, not per-row (batches are efficient)
EXECUTE FUNCTION notify_event_published();
```

**Lambda Handler:**

```python
# lambda_handler.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django
django.setup()

from django.core.management import call_command

def handler(event, context):
    """
    Invoked by Aurora trigger or CloudWatch schedule.
    Processes pending events in the outbox.
    """
    call_command("publish_events", "--once", "--batch-size=100")
    return {"statusCode": 200}
```

> [!NOTE]
> The Lambda code is the same regardless of trigger source. Aurora triggers provide sub-second delivery; a CloudWatch schedule can serve as a fallback if needed.

---

## FIFO Ordering

For consumers that require per-aggregate ordering (e.g., state machines), use SQS FIFO with `MessageGroupId`:

### EventBridge Pipes → SQS FIFO

```python
# CDK example
from aws_cdk import aws_sqs as sqs, aws_pipes as pipes

fifo_queue = sqs.Queue(
    self, "OrderedEventsQueue",
    queue_name="ordered-events.fifo",
    fifo=True,
    content_based_deduplication=True,
)

# Pipe: EventBridge → SQS FIFO with MessageGroupId = aggregate_id
pipe = pipes.CfnPipe(
    self, "OrderedEventsPipe",
    source=event_bus.event_bus_arn,
    target=fifo_queue.queue_arn,
    target_parameters=pipes.CfnPipe.PipeTargetParametersProperty(
        sqs_queue_parameters=pipes.CfnPipe.PipeTargetSqsQueueParametersProperty(
            message_group_id="$.detail.aggregate_id",
        )
    ),
)
```

### When to Use FIFO

| Scenario | Use FIFO? |
|----------|-----------|
| Webhook delivery | No (order doesn't matter) |
| Notification sending | No |
| Aggregate state rebuilding | **Yes** |
| Workflow state machines | **Yes** |
| Analytics ingestion | No (usually) |

---

## Schema Validation

### In-Repo JSON Schemas

Store schemas in `/schemas/events/` and validate on publish:

```
schemas/events/
├── time_entry.created.v1.json
├── time_entry.approved.v1.json
└── public.time_entry.created.v1.json
```

### Example Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "time_entry.created.v1",
  "type": "object",
  "required": ["event_id", "event_type", "schema_version", "workspace_id", "data"],
  "properties": {
    "event_id": { "type": "string", "format": "uuid" },
    "event_type": { "const": "time_entry.created" },
    "schema_version": { "const": 1 },
    "workspace_id": { "type": "string", "pattern": "^org_" },
    "data": {
      "type": "object",
      "required": ["id", "description"],
      "properties": {
        "id": { "type": "string", "pattern": "^te_" },
        "description": { "type": "string" }
      },
      "additionalProperties": true
    }
  }
}
```

### Validation on Publish

```python
import jsonschema

PUBLIC_EVENT_PREFIX = "public."

def is_public_event(event_type: str) -> bool:
    """
    Determine whether an event type should be treated as public.
    Centralizes classification logic instead of ad-hoc string checks.
    """
    return event_type.strip().startswith(PUBLIC_EVENT_PREFIX)

def publish_event(event: dict):
    """Validate schema before publishing."""
    schema = load_schema(event["event_type"], event["schema_version"])
    jsonschema.validate(event, schema)

    # Guard: workspace_id required for all public events
    if is_public_event(event["event_type"]):
        assert event.get("workspace_id"), "workspace_id required for public events"

    OutboxEvent.objects.create(
        event_type=event["event_type"],
        payload=event,
        ...
    )
```

### Enforcing Additive Changes

CI check to prevent breaking schema changes:

```bash
# .github/workflows/schema-check.yml
- name: Check schema compatibility
  run: |
    python scripts/check_schema_compatibility.py \
      --old origin/main:schemas/events/ \
      --new schemas/events/
```

---

## Tenant Scoping Guards

> [!CAUTION]
> All public events **must** include `workspace_id`. Reject events without it to prevent data leakage.

### Publishing Guard

```python
def create_public_event(internal_event: dict) -> dict:
    """Transform internal event to public event with guards."""

    # REQUIRED: workspace_id
    workspace_id = internal_event.get("workspace_id")
    if not workspace_id:
        raise ValueError("Cannot publish public event without workspace_id")

    # Strip PII by default (explicit allowlist)
    allowed_fields = PUBLIC_EVENT_ALLOWLIST.get(internal_event["event_type"], set())

    public_data = {
        k: v for k, v in internal_event["data"].items()
        if k in allowed_fields
    }

    return {
        "event_type": f"public.{internal_event['event_type']}",
        "workspace_id": workspace_id,
        "data": public_data,
        ...
    }
```

### Public Event Allowlist

```python
PUBLIC_EVENT_ALLOWLIST = {
    "time_entry.created": {"id", "description", "project_id", "duration_minutes", "created_at"},
    "time_entry.approved": {"id", "approved_by_id", "approved_at"},
    # Explicitly exclude: user emails, internal IDs, etc.
}
```

---

## Observability

### Tracing

Propagate `correlation_id` through all systems:

```python
# Django middleware
class CorrelationIdMiddleware:
    def __call__(self, request):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.correlation_id = correlation_id

        # Set in logging context
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        # Propagate to AWS X-Ray
        xray_recorder.put_annotation("correlation_id", correlation_id)

        response = self.get_response(request)
        response["X-Correlation-ID"] = correlation_id
        return response
```

### SLOs

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Outbox publish latency (p99) | < 5s | > 10s |
| EventBridge delivery success | > 99.9% | < 99.5% |
| DLQ depth | 0 | > 10 messages |
| Webhook delivery success | > 99% | < 95% |

### Metrics to Emit

```python
# Using CloudWatch EMF or StatsD
metrics.count("events.published", tags={"event_type": event_type})
metrics.count("events.delivery.success", tags={"consumer": consumer_name})
metrics.count("events.delivery.failure", tags={"consumer": consumer_name, "error": error_type})
metrics.gauge("events.dlq.depth", dlq.approximate_number_of_messages)
```

---

## High Availability

### Multi-AZ Configuration

| Component | HA Strategy |
|-----------|-------------|
| EventBridge | Regional service, inherently HA |
| SQS | Cross-AZ, automatic |
| RDS/Aurora | Multi-AZ deployment, automatic failover |
| Lambda | Multi-AZ by default |
| ECS/Django | Multi-AZ ALB + task placement |

### DLQ Redrive Policy

```python
from aws_cdk import aws_sqs as sqs

main_queue = sqs.Queue(
    self, "IntegrationQueue",
    visibility_timeout=Duration.seconds(300),  # Match Lambda timeout
    dead_letter_queue=sqs.DeadLetterQueue(
        max_receive_count=3,  # Move to DLQ after 3 failures
        queue=dlq,
    ),
)

# Parking queue for poison messages (after DLQ redrive fails)
parking_queue = sqs.Queue(
    self, "ParkingQueue",
    queue_name="integration-parking",
    retention_period=Duration.days(14),
)
```

### RDS Connection Management

For Lambda accessing RDS:

```python
# CDK: Use RDS Proxy
rds_proxy = rds.DatabaseProxy(
    self, "RDSProxy",
    vpc=vpc,
    secrets=[db_secret],
    db_proxy_name="app-proxy",
    require_tls=True,
)

# Lambda connects to proxy, not directly to RDS
lambda_fn.add_environment("DATABASE_HOST", rds_proxy.endpoint)
```

### Cross-Region (Future)

For disaster recovery:

```
Primary Region (us-east-1)          Backup Region (us-west-2)
┌─────────────────────┐              ┌─────────────────────┐
│ EventBridge         │──replicate──▶│ EventBridge         │
│ Aurora (primary)    │──replicate──▶│ Aurora (replica)    │
└─────────────────────┘              └─────────────────────┘
```

Use EventBridge global endpoints for automatic failover.
