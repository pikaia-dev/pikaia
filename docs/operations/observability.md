# Observability: Logging, Events, and Audit Trails

This document explains the three observability systems in this starter template, their purposes, and how they work together.

## Overview

| System | Purpose | Audience | Retention | Example |
|--------|---------|----------|-----------|---------|
| **Structured Logging** | Operational debugging | Developers, SREs | Days/weeks | "Request took 150ms, returned 500" |
| **Domain Events** | Business event delivery | Downstream systems | Processed then purged | `subscription.activated` |
| **Audit Log** | Compliance, user activity | Admins, compliance, users | Permanent | "Alice invited bob@example.com" |

## Structured Logging

### What It Is

Structured logging outputs machine-readable JSON logs with consistent field names. Every log entry includes:

- **Correlation ID** (`trace_id`) - Links all logs from a single request
- **User context** (`usr.id`, `usr.email`) - Who made the request
- **Organization context** (`organization.id`) - Multi-tenant filtering
- **Request metadata** (`http.method`, `http.url_details.path`, `http.status_code`)
- **Timing** (`duration`) - Request latency in nanoseconds

### Why JSON?

```json
{
  "timestamp": "2026-01-17T10:23:45.123Z",
  "level": "ERROR",
  "logger": "apps.billing.webhooks",
  "event": "stripe_webhook_handler_error",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "usr.id": "123",
  "organization.id": "org_abc",
  "http.method": "POST",
  "http.url_details.path": "/api/v1/billing/webhook",
  "http.status_code": 500,
  "duration": 152000000,
  "exc_info": "Traceback (most recent call last):..."
}
```

Benefits:
1. **Queryable** - Filter by any field in CloudWatch Logs Insights, Datadog, or Elastic
2. **Traceable** - Follow a request across services using `trace_id`
3. **Alertable** - Set up alerts on specific event types or error patterns
4. **Dashboardable** - Build latency percentiles, error rates, etc.

### Field Naming Convention

We use [Datadog Standard Attributes](https://docs.datadoghq.com/logs/log_configuration/attributes_naming_convention/) for automatic integrations:

| Field | Datadog Feature | Example |
|-------|-----------------|---------|
| `trace_id` | APM trace linking | `550e8400-e29b-...` |
| `usr.id` | User sessions | `user_123` |
| `usr.email` | User lookup | `alice@example.com` |
| `http.method` | HTTP dashboards | `POST` |
| `http.status_code` | Error tracking | `500` |
| `duration` | Latency analysis | `152000000` (ns) |

### Usage

```python
from apps.core.logging import get_logger

logger = get_logger(__name__)

# Basic structured log
logger.info("user_created", user_id="123", email="alice@example.com")

# With exception
try:
    process_payment()
except PaymentError:
    logger.exception("payment_processing_failed", amount=100, currency="USD")
```

### Configuration

**Production** (`config/settings/production.py`):
```python
from apps.core.logging import configure_logging
configure_logging(json_format=True, log_level="INFO")
```

**Development** (`config/settings/local.py`):
```python
from apps.core.logging import configure_logging
configure_logging(json_format=False, log_level="DEBUG")  # Pretty console output
```

### Context Binding

Context is automatically bound by middleware:

1. **CorrelationIdMiddleware** binds:
   - `correlation_id` (renamed to `trace_id` for Datadog)
   - `http.method`
   - `http.url_details.path`
   - `duration_ms` (converted to `duration` in nanoseconds)
   - `http.status_code`

2. **StytchAuthMiddleware** binds (after successful auth):
   - `usr.id`
   - `usr.email`
   - `organization.id`

All subsequent logs within that request automatically include this context.

### CloudWatch Logs Insights Queries

```sql
-- Find slow requests
fields @timestamp, `trace_id`, `http.url_details.path`, duration/1000000 as duration_ms
| filter duration > 1000000000
| sort duration desc
| limit 20

-- Find errors for a user
fields @timestamp, event, @message
| filter `usr.id` = "user_123" and level = "ERROR"
| sort @timestamp desc

-- Request volume by endpoint
stats count(*) as requests by `http.url_details.path`
| sort requests desc
```

---

## Domain Events (OutboxEvent)

### What It Is

Domain events represent **business occurrences** that other parts of the system (or external systems) need to react to:

- `member.invited` - Trigger welcome email
- `subscription.activated` - Update billing dashboard
- `member.role_changed` - Update permissions cache

### How It Works

```
[Business Logic] → [OutboxEvent table] → [Publisher] → [EventBridge] → [Consumers]
                    (transactional)       (polling)
```

1. **Transactional Outbox**: Events are written to `OutboxEvent` table in the same transaction as business data
2. **Publisher**: Background process polls the table and publishes to EventBridge (or logs locally)
3. **Consumers**: Lambda functions or other services process events

### Usage

```python
from apps.events.services import publish_event

# Inside a transaction
with transaction.atomic():
    member = Member.objects.create(...)

    publish_event(
        event_type="member.invited",
        aggregate=member,
        data={"email": "bob@example.com", "role": "member"},
        actor=request.auth_user,  # Who triggered this
    )
```

### Event Schema

```json
{
  "event_id": "uuid",
  "event_type": "member.invited",
  "schema_version": 1,
  "occurred_at": "2026-01-17T10:23:45.123Z",
  "aggregate_type": "member",
  "aggregate_id": "456",
  "organization_id": "org_abc",
  "correlation_id": "550e8400-e29b-...",
  "actor": {
    "type": "user",
    "id": "123",
    "email": "alice@example.com"
  },
  "data": {
    "email": "bob@example.com",
    "role": "member"
  }
}
```

### Events vs Logging

| Aspect | Events | Logs |
|--------|--------|------|
| **Durability** | Guaranteed delivery (retries) | Best-effort |
| **Consumers** | Other services, webhooks | Humans, dashboards |
| **Schema** | Versioned, validated | Free-form |
| **Retention** | Processed then purged | Days/weeks |
| **Purpose** | Trigger side effects | Debug issues |

**Use events when**: Another system needs to react (send email, update cache, sync to external service)

**Use logging when**: You need to debug what happened, monitor performance, or alert on errors

---

## Audit Log

### What It Is

Audit logs are **permanent records** of user actions for compliance and accountability:

- Who did what and when
- What changed (before/after diff)
- From where (IP address, user agent)

### How It Works

```python
from apps.events.services import create_audit_log

create_audit_log(
    action="member.role_changed",
    aggregate=member,
    actor=request.auth_user,
    diff={
        "old": {"role": "member"},
        "new": {"role": "admin"},
    },
    ip_address=get_client_ip(request),
    user_agent=request.META.get("HTTP_USER_AGENT"),
)
```

### Audit Log Schema

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | Action type (e.g., `member.role_changed`) |
| `aggregate_type` | string | Model type (e.g., `member`) |
| `aggregate_id` | string | Model ID |
| `organization_id` | string | Organization scope |
| `actor_id` | string | User who performed action |
| `actor_email` | string | User email (denormalized) |
| `correlation_id` | uuid | Links to request logs |
| `diff` | jsonb | `{"old": {...}, "new": {...}}` |
| `ip_address` | string | Client IP |
| `user_agent` | string | Browser/client info |
| `created_at` | timestamp | When it happened |

### Audit Log vs Events

| Aspect | Audit Log | Events |
|--------|-----------|--------|
| **Retention** | Permanent (years) | Short-term |
| **Purpose** | Compliance, investigation | Side effects |
| **Audience** | Admins, auditors, users | Systems |
| **Trigger** | User actions | Business logic |
| **Contains** | Change diff, actor, IP | Event data |

**Use audit logs for**: Recording who changed what for compliance (GDPR, SOC2)

**Use events for**: Triggering downstream actions (emails, syncs)

---

## How They Work Together

Consider a member invite flow:

```
1. User clicks "Invite"
   ↓
2. API endpoint executes
   ├── LOG: "member_invite_started" (debug info)
   │
3. Business logic runs
   ├── EVENT: "member.invited" → triggers welcome email
   ├── AUDIT: "member.invited" → permanent record
   │
4. Response sent
   ├── LOG: "request_completed" (timing, status)
```

All three share the **correlation_id**, so you can:
- See the audit record: "Alice invited Bob"
- Find the event: Check if welcome email was sent
- Debug issues: See all logs from that request

### Correlation Flow

```
Request arrives
    │
    ▼
CorrelationIdMiddleware
    │ bind: trace_id, http.method, http.url_details.path
    │
    ▼
StytchAuthMiddleware
    │ bind: usr.id, usr.email, organization.id
    │
    ▼
View executes
    │ - Logs include all context automatically
    │ - Events include correlation_id
    │ - Audit logs include correlation_id
    │
    ▼
CorrelationIdMiddleware
    │ bind: duration, http.status_code
    │ clear: context (prevent leakage)
    │
    ▼
Response sent
```

---

## Best Practices

### Logging

1. **Use event names, not sentences**:
   ```python
   # Good
   logger.info("user_created", user_id=user.id)

   # Bad
   logger.info(f"Created user {user.id}")
   ```

2. **Include relevant context as key-value pairs**:
   ```python
   logger.error(
       "payment_failed",
       stripe_error_code=e.code,
       amount=amount,
       currency=currency,
   )
   ```

3. **Use appropriate log levels**:
   - `DEBUG`: Detailed info for debugging
   - `INFO`: Normal operations (request handled, job completed)
   - `WARNING`: Unexpected but handled (retrying, using fallback)
   - `ERROR`: Something failed but system continues
   - `EXCEPTION`: Error with stack trace

### Events

1. **Past tense for event names**: `member.invited`, not `member.invite`
2. **Include enough context to process independently**: Don't rely on external lookups
3. **Version your schemas**: Use `schema_version` for backwards compatibility
4. **Keep payloads under 256KB**: EventBridge limit

### Audit Logs

1. **Record the diff**: `{"old": {...}, "new": {...}}`
2. **Denormalize actor email**: Email might change later
3. **Include IP and user agent**: Required for security investigations
4. **Never delete audit logs**: They're your compliance record

---

## Querying Examples

### "Why did this request fail?"

1. Get the correlation ID from error alert
2. Query logs:
   ```sql
   fields @timestamp, event, @message
   | filter trace_id = "550e8400-e29b-..."
   | sort @timestamp
   ```

### "What did this user do?"

1. Query audit log:
   ```sql
   SELECT * FROM events_auditlog
   WHERE actor_id = 'user_123'
   ORDER BY created_at DESC;
   ```

### "Did the welcome email send?"

1. Find the event:
   ```sql
   SELECT * FROM events_outboxevent
   WHERE event_type = 'member.invited'
   AND payload->>'data'->>'email' = 'bob@example.com';
   ```

2. Check if published (status = 'published')

---

## CloudWatch Monitoring

### Overview

The `PikaiaObservability` CDK stack deploys CloudWatch dashboards and alarms for operational monitoring.

### Dashboard: `pikaia-operations`

The main operations dashboard includes:

| Row | Widgets |
|-----|---------|
| **API Overview** | Request rate, 5xx errors, latency (p50, p99) |
| **ECS Service** | CPU utilization, memory utilization, healthy host count |
| **Database** | Connections, CPU, ACU capacity, read/write latency |
| **Alarms** | Status of all configured alarms |

Access: `https://{region}.console.aws.amazon.com/cloudwatch/home#dashboards:name=pikaia-operations`

### Alarms

| Alarm | Condition | Evaluation |
|-------|-----------|------------|
| `pikaia-high-error-rate` | 5xx errors > 5% of requests | 2 periods of 5 min |
| `pikaia-high-latency` | p99 response time > 2 seconds | 3 periods of 1 min |
| `pikaia-unhealthy-hosts` | Healthy hosts < 1 | 2 periods of 1 min |
| `pikaia-ecs-high-cpu` | ECS CPU > 85% | 3 periods of 1 min |
| `pikaia-ecs-high-memory` | ECS memory > 85% | 3 periods of 1 min |
| `pikaia-db-high-cpu` | Database CPU > 80% | 3 periods of 1 min |
| `pikaia-db-high-connections` | DB connections > 500 | 2 periods of 1 min |

All alarms notify the `pikaia-alarms` SNS topic.

### Deployment

```bash
# Deploy with alarm email notifications
cdk deploy PikaiaObservability --context alarm_email=ops@example.com

# Deploy all stacks (observability depends on PikaiaApp)
cdk deploy --all
```

### Customization

The observability stack is defined in `infra/stacks/observability_stack.py`. Common customizations:

**Adjust alarm thresholds:**
```python
latency_alarm = cloudwatch.Alarm(
    ...
    threshold=3,  # Change from 2 to 3 seconds
    evaluation_periods=5,  # More periods before alarming
)
```

**Add custom metrics:**
```python
custom_metric = cloudwatch.Metric(
    namespace="Custom/MyApp",
    metric_name="OrdersProcessed",
    statistic="Sum",
    period=Duration.minutes(1),
)
dashboard.add_widgets(
    cloudwatch.GraphWidget(title="Orders", left=[custom_metric])
)
```

**Add PagerDuty/Slack notifications:**
```python
# Instead of email, use HTTPS endpoint for PagerDuty/Slack
alarm_topic.add_subscription(
    sns.subscriptions.UrlSubscription("https://events.pagerduty.com/...")
)
```

### Correlation with Logs

When an alarm fires:

1. Note the **time window** from the alarm
2. Query CloudWatch Logs Insights for that period:
   ```sql
   fields @timestamp, trace_id, event, @message
   | filter @timestamp >= "2026-01-17T10:00:00"
   | filter level = "ERROR"
   | sort @timestamp
   ```
3. Use `trace_id` to find all logs from problematic requests
