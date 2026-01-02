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
| `event_type` | string | Semantic event name | `"time_entry.created"` |
| `schema_version` | integer | Payload version | `1` |
| `occurred_at` | ISO 8601 | When the event happened (business time) | `"2025-01-02T23:00:00Z"` |
| `aggregate_id` | string | Entity identity | `"te_01HN8J9K..."` |
| `aggregate_type` | string | Entity type | `"time_entry"` |
| `correlation_id` | UUID | Request trace ID | `"req_01HN8J..."` |
| `actor` | object | Who caused the event | `{"type": "user", "id": "usr_01HN..."}` |
| `workspace_id` | string | Organization/tenant ID | `"org_01HN..."` |

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
  "event_type": "time_entry.created",
  "schema_version": 1,
  "occurred_at": "2025-01-02T23:00:00Z",
  "aggregate_id": "te_01HN8J9K2M3N4P5Q6R7S8T9U0V",
  "aggregate_type": "time_entry",
  "workspace_id": "org_01HN8J9K2M3N4P5Q6R7S8T9U0V",
  "correlation_id": "req_01HN8J9K2M3N4P5Q6R7S8T9U0V",
  "actor": {
    "type": "user",
    "id": "usr_01HN8J9K2M3N4P5Q6R7S8T9U0V",
    "email": "user@example.com"
  },
  "data": {
    "description": "Working on feature X",
    "project_id": "prj_01HN...",
    "duration_minutes": 45
  }
}
```

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

## Future Considerations

- **Transactional Outbox**: If event loss becomes an issue, implement outbox pattern with `OutboxEvent` table
- **Schema Registry**: For complex multi-team scenarios, consider AWS Glue Schema Registry or Confluent
- **Event Replay UI**: Admin interface to replay failed events from DLQ
