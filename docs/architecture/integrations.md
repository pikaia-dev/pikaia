# Integration Architecture

This document defines the integration strategy for external webhooks, automation platforms, and third-party services.

## Table of Contents

- [Overview](#overview)
- [Integration Router](#integration-router)
- [Webhook Delivery](#webhook-delivery)
- [Security](#security)
- [Data Models](#data-models)
- [Supported Platforms](#supported-platforms)
- [Inbound Webhooks](#inbound-webhooks)

---

## Overview

The integration architecture enables customers to connect their workspaces to external tools (Zapier, Slack, custom systems) via outbound webhooks. This is implemented as a **product feature**, not infrastructure.

### Design Principles

| Principle | Implementation |
|-----------|----------------|
| Webhooks as v1 | Generic outbound webhooks, works with any automation platform |
| No per-customer EventBridge rules | Single integration router, routing logic in app code |
| Public events only | Curated subset of internal events for external consumption |
| At-least-once delivery | Retries with exponential backoff, DLQ for failures |

### Integration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Internal Events                              │
│   time_entry.created, user.invited, subscription.activated      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EventBridge                                 │
│           Rule: {"detail-type": [{"prefix": "public."}]}         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Integration Router                             │
│                      (SQS + Lambda)                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Match event │  │ Apply       │  │ Deliver to  │              │
│  │ to subs     │  │ filters     │  │ endpoints   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     ┌─────────┐    ┌─────────┐    ┌─────────┐
     │  Zapier │    │  Slack  │    │ Custom  │
     │ Webhook │    │ Webhook │    │ Webhook │
     └─────────┘    └─────────┘    └─────────┘
```

---

## Integration Router

### Why One Router, Not Per-Customer Rules

| Approach | Pros | Cons |
|----------|------|------|
| EventBridge rule per subscription | Pure infra | Rule limits (300/bus), complex management |
| Single router with DB routing | Simple, scalable | Slightly more code |

**Decision**: Single router with routing logic in application code.

### Router Responsibilities

1. **Receive public events** from EventBridge via SQS
2. **Query active subscriptions** matching event type and workspace
3. **Apply filters** (per-subscription filtering logic)
4. **Deliver webhooks** with retries
5. **Record delivery logs** for debugging
6. **DLQ failed events** for manual review

### Router Architecture

```python
# Lambda handler (simplified)
def handle_integration_event(event: dict, context):
    """
    Process public event and deliver to matching subscriptions.
    """
    for record in event["Records"]:
        message = json.loads(record["body"])
        event_data = json.loads(message["detail"])

        workspace_id = event_data["workspace_id"]
        event_type = event_data["event_type"]

        # Find matching subscriptions
        subscriptions = IntegrationSubscription.objects.filter(
            workspace_id=workspace_id,
            event_types__contains=[event_type],
            is_active=True,
        )

        for sub in subscriptions:
            # Apply subscription-specific filters
            if not sub.matches_filters(event_data):
                continue

            # Deliver webhook
            deliver_webhook.delay(
                subscription_id=sub.id,
                event_data=event_data,
            )
```

---

## Webhook Delivery

### Delivery Flow

```
1. Router queues delivery task
2. Worker fetches endpoint details
3. Worker signs payload (HMAC-SHA256)
4. Worker sends HTTP POST
5. Worker records result
6. On failure: retry with backoff
7. After max retries: move to DLQ
```

### HTTP Request Format

```http
POST /webhook-receiver HTTP/1.1
Host: customer-app.example.com
Content-Type: application/json
X-Webhook-ID: wh_01HN8J9K2M3N4P5Q6R7S8T9U0V
X-Webhook-Timestamp: 1704236400
X-Webhook-Signature: sha256=abc123...
User-Agent: TangoWebhooks/1.0

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
    "duration_minutes": 45
  }
}
```

### Retry Policy

| Attempt | Delay | Cumulative |
|---------|-------|------------|
| 1 (initial) | 0s | 0s |
| 2 | 1s + jitter | ~1s |
| 3 | 4s + jitter | ~5s |
| 4 | 16s + jitter | ~21s |
| 5 | 64s + jitter | ~85s |
| 6 | 256s + jitter | ~6min |
| 7 (final) | 1024s + jitter | ~23min |

After 7 attempts (~23 minutes), event moves to DLQ.

### Success Criteria

| Response | Action |
|----------|--------|
| `2xx` | Success, record delivery |
| `410 Gone` | Disable subscription (endpoint removed) |
| `429` | Retry with `Retry-After` header if present |
| `4xx` (other) | Fail permanently (bad request) |
| `5xx` | Retry with backoff |
| Timeout (10s) | Retry with backoff |

---

## Security

### HMAC Signature Verification

**Signing (server-side):**

```python
import hmac
import hashlib
import time

def sign_webhook(payload: str, secret: str, timestamp: int) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.
    """
    message = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"
```

**Verification (client-side):**

```python
def verify_webhook(payload: str, signature: str, secret: str, timestamp: int) -> bool:
    """
    Verify webhook signature and check timestamp.
    """
    # Check timestamp (5-minute window)
    now = int(time.time())
    if abs(now - timestamp) > 300:
        return False  # Replay attack prevention

    expected = sign_webhook(payload, secret, timestamp)
    return hmac.compare_digest(signature, expected)
```

### Secret Rotation

- Each subscription has a unique signing secret
- Secrets can be rotated without downtime:
  1. Generate new secret
  2. Accept signatures from both secrets (transition period)
  3. Customer updates their verification
  4. Remove old secret

### Additional Security Measures

| Measure | Implementation |
|---------|----------------|
| HTTPS only | Reject HTTP endpoints on subscription creation |
| Timestamp validation | Reject requests older than 5 minutes |
| IP allowlisting (future) | Optional per-subscription IP filter |
| Rate limiting | Per-workspace delivery rate limits |

---

## Data Models

### IntegrationEndpoint

```python
class IntegrationEndpoint(models.Model):
    """
    Webhook endpoint configuration.
    """
    id = models.CharField(max_length=50, primary_key=True)  # "ep_01HN..."
    workspace = models.ForeignKey(Organization, on_delete=models.CASCADE)

    name = models.CharField(max_length=100)  # "Slack Notifications"
    url = models.URLField()

    # Security
    signing_secret = models.CharField(max_length=64)
    signing_secret_rotated = models.CharField(max_length=64, blank=True)  # During rotation

    # Status
    is_active = models.BooleanField(default=True)
    disabled_at = models.DateTimeField(null=True)
    disabled_reason = models.CharField(max_length=100, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "is_active"]),
        ]
```

### IntegrationSubscription

```python
class IntegrationSubscription(models.Model):
    """
    Maps event types to an endpoint with optional filters.
    """
    id = models.CharField(max_length=50, primary_key=True)  # "sub_01HN..."
    endpoint = models.ForeignKey(IntegrationEndpoint, on_delete=models.CASCADE)

    # Event matching
    event_types = models.JSONField()  # ["public.time_entry.created", "public.time_entry.approved"]

    # Optional filters (applied in router)
    filters = models.JSONField(default=dict)  # {"project_id": "prj_01HN..."}

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["endpoint", "is_active"]),
        ]

    def matches_filters(self, event_data: dict) -> bool:
        """Check if event matches subscription filters."""
        for key, value in self.filters.items():
            if event_data.get("data", {}).get(key) != value:
                return False
        return True
```

### IntegrationDelivery

```python
class IntegrationDelivery(models.Model):
    """
    Delivery attempt log for debugging and replay.
    """
    id = models.CharField(max_length=50, primary_key=True)  # "del_01HN..."
    subscription = models.ForeignKey(IntegrationSubscription, on_delete=models.CASCADE)

    # Event reference
    event_id = models.UUIDField()
    event_type = models.CharField(max_length=100)

    # Delivery status
    status = models.CharField(max_length=20)  # pending, success, failed, dlq
    attempts = models.PositiveIntegerField(default=0)

    # Response details
    response_status = models.PositiveIntegerField(null=True)
    response_body = models.TextField(blank=True)  # First 1KB for debugging
    response_time_ms = models.PositiveIntegerField(null=True)

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True)
    next_retry_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=["subscription", "created_at"]),
            models.Index(fields=["status", "next_retry_at"]),  # Retry query
        ]
```

---

## Supported Platforms

### Out-of-the-Box Compatibility

By implementing generic webhooks, the bootstrap supports:

| Platform | Integration Method |
|----------|-------------------|
| **Zapier** | Catch Hook trigger (paste URL) |
| **Make (Integromat)** | Custom Webhook module |
| **n8n** | Webhook trigger node |
| **Pabbly Connect** | Webhook trigger |
| **Slack** | Incoming Webhooks |
| **Microsoft Teams** | Incoming Webhooks |
| **Discord** | Webhooks |
| **Custom systems** | Any HTTP endpoint |

### Future: Zapier OAuth App

For a polished Zapier experience:

1. Build OAuth flow (Stytch-based)
2. Register Zapier app with triggers
3. Zapier manages auth, shows available triggers in UI

This is a UX enhancement, not a technical requirement. Generic webhooks work with Zapier Catch Hooks immediately.

---

## Inbound Webhooks

### Stripe Webhooks (Existing)

Already implemented in `apps/billing/`:

```python
# apps/billing/api.py
@router.post("/webhooks/stripe")
def stripe_webhook(request):
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    # Handle event
    handle_stripe_event(event)
    return HttpResponse(status=200)
```

### Stytch Webhooks (Future)

For real-time auth events:

```python
@router.post("/webhooks/stytch")
def stytch_webhook(request):
    # Verify signature using Stytch SDK
    # Handle: member.created, member.deleted, organization.updated
    ...
```

### Inbound Webhook Best Practices

| Practice | Implementation |
|----------|----------------|
| Signature verification | HMAC or vendor-specific |
| Idempotency | Store processed event IDs |
| Fast ACK | Return 200 quickly, process async |
| Retry tolerance | Handle duplicate deliveries |

---

## API Endpoints

### List Endpoints

```
GET /api/v1/integrations/endpoints
```

### Create Endpoint

```
POST /api/v1/integrations/endpoints
{
  "name": "Production Slack",
  "url": "https://hooks.slack.com/services/..."
}
```

Response includes generated `signing_secret`.

### Create Subscription

```
POST /api/v1/integrations/endpoints/{endpoint_id}/subscriptions
{
  "event_types": ["public.time_entry.created", "public.time_entry.approved"],
  "filters": {
    "project_id": "prj_01HN..."
  }
}
```

### List Deliveries (Debug)

```
GET /api/v1/integrations/endpoints/{endpoint_id}/deliveries?status=failed
```

### Replay Delivery

```
POST /api/v1/integrations/deliveries/{delivery_id}/replay
```

---

## Rate Limiting & Tenant Isolation

### Per-Tenant Rate Limiting

Prevent noisy neighbors from overwhelming the delivery infrastructure:

```python
class TenantRateLimiter:
    """
    Token bucket rate limiter per workspace.
    Uses DynamoDB for distributed state.
    """

    def __init__(self, table_name: str = "rate-limits"):
        self.table = boto3.resource("dynamodb").Table(table_name)

    def check_and_consume(self, workspace_id: str, tokens: int = 1) -> bool:
        """
        Check rate limit and consume tokens.
        Default: 100 webhooks/minute per workspace.
        """
        now = int(time.time())
        bucket_key = f"webhook:{workspace_id}:{now // 60}"  # Per-minute bucket

        try:
            response = self.table.update_item(
                Key={"pk": bucket_key},
                UpdateExpression="ADD #tokens :t",
                ExpressionAttributeNames={"#tokens": "tokens"},
                ExpressionAttributeValues={":t": tokens, ":max": 100},
                ConditionExpression="attribute_not_exists(#tokens) OR #tokens < :max",
                ReturnValues="UPDATED_NEW",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False  # Rate limited
            raise
```

### Per-Endpoint Concurrency

Limit in-flight requests to prevent overwhelming slow endpoints:

```python
MAX_IN_FLIGHT_PER_ENDPOINT = 10

async def deliver_with_concurrency_limit(endpoint_id: str, event: dict):
    semaphore = get_endpoint_semaphore(endpoint_id, MAX_IN_FLIGHT_PER_ENDPOINT)

    async with semaphore:
        await deliver_webhook(endpoint_id, event)
```

---

## Circuit Breaker

Auto-disable endpoints after repeated failures to protect delivery infrastructure:

### Circuit States

```
CLOSED → failures exceed threshold → OPEN → cooldown expires → HALF_OPEN → success → CLOSED
                                              ↓ failure
                                            OPEN
```

### Implementation

```python
class EndpointCircuitBreaker:
    """
    Circuit breaker per endpoint.
    """
    FAILURE_THRESHOLD = 5  # consecutive failures
    COOLDOWN_SECONDS = 300  # 5 minutes

    def record_failure(self, endpoint: IntegrationEndpoint):
        endpoint.consecutive_failures += 1

        if endpoint.consecutive_failures >= self.FAILURE_THRESHOLD:
            endpoint.is_active = False
            endpoint.disabled_at = timezone.now()
            endpoint.disabled_reason = "circuit_breaker: consecutive failures"
            logger.warning(f"Circuit opened for endpoint {endpoint.id}")

        endpoint.save()

    def record_success(self, endpoint: IntegrationEndpoint):
        endpoint.consecutive_failures = 0
        endpoint.save()

    def maybe_retry(self, endpoint: IntegrationEndpoint) -> bool:
        """Check if disabled endpoint should be retried (half-open)."""
        if not endpoint.disabled_at:
            return True

        cooldown_expired = timezone.now() > endpoint.disabled_at + timedelta(
            seconds=self.COOLDOWN_SECONDS
        )
        return cooldown_expired
```

### Model Updates

Add to `IntegrationEndpoint`:

```python
consecutive_failures = models.PositiveIntegerField(default=0)
```

---

## Secret Management

### AWS Secrets Manager

Store signing secrets in Secrets Manager, not in the database:

```python
import boto3

secrets_client = boto3.client("secretsmanager")

def get_signing_secret(endpoint_id: str) -> str:
    """Retrieve signing secret from Secrets Manager."""
    secret_id = f"webhook/{endpoint_id}/signing-secret"
    response = secrets_client.get_secret_value(SecretId=secret_id)
    return response["SecretString"]

def create_signing_secret(endpoint_id: str) -> str:
    """Create new signing secret in Secrets Manager."""
    secret = secrets.token_urlsafe(32)
    secrets_client.create_secret(
        Name=f"webhook/{endpoint_id}/signing-secret",
        SecretString=secret,
    )
    return secret
```

### Scheduled Rotation

```python
# Lambda triggered by CloudWatch Events (every 90 days)
def rotate_signing_secret(event, context):
    """Rotate signing secrets with dual-secret verification window."""
    endpoint_id = event["endpoint_id"]

    # 1. Generate new secret
    new_secret = secrets.token_urlsafe(32)

    # 2. Update Secrets Manager with staged secret
    secrets_client.put_secret_value(
        SecretId=f"webhook/{endpoint_id}/signing-secret",
        SecretString=new_secret,
        VersionStages=["AWSPENDING"],
    )

    # 3. During transition period, accept signatures from both secrets
    # (Already supported via signing_secret_rotated field)
```

---

## Replay Tooling

### Replay from DLQ

```python
# Lambda: Replay failed deliveries with rate limiting
def replay_from_dlq(event, context):
    """
    Replay deliveries from DLQ with selective filtering.
    """
    filters = event.get("filters", {})
    rate_limit = event.get("rate_limit", 10)  # per second

    dlq = sqs.Queue(DELIVERY_DLQ_URL)
    replayed = 0

    for message in dlq.receive_messages(MaxNumberOfMessages=10):
        delivery = json.loads(message.body)

        # Apply filters
        if filters.get("workspace_id") and delivery["workspace_id"] != filters["workspace_id"]:
            continue
        if filters.get("event_type") and delivery["event_type"] != filters["event_type"]:
            continue

        # Re-queue for delivery
        deliver_webhook.delay(
            subscription_id=delivery["subscription_id"],
            event_data=delivery["event_data"],
        )

        message.delete()
        replayed += 1

        # Rate limiting
        time.sleep(1 / rate_limit)

    return {"replayed": replayed}
```

### API Endpoint

```
POST /api/v1/integrations/deliveries/replay
{
  "filters": {
    "workspace_id": "org_01HN...",
    "status": "failed",
    "since": "2025-01-01T00:00:00Z"
  },
  "rate_limit": 10
}
```

---

## Observability

### Delivery Metrics

Emit structured metrics for every delivery attempt:

```python
def emit_delivery_metrics(delivery: IntegrationDelivery, duration_ms: int):
    """Emit CloudWatch metrics for delivery."""
    dimensions = [
        {"Name": "EventType", "Value": delivery.event_type},
        {"Name": "WorkspaceId", "Value": delivery.subscription.endpoint.workspace_id},
        {"Name": "Status", "Value": "success" if delivery.status == "success" else "failure"},
    ]

    cloudwatch.put_metric_data(
        Namespace="Integrations",
        MetricData=[
            {
                "MetricName": "DeliveryCount",
                "Value": 1,
                "Unit": "Count",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "DeliveryLatency",
                "Value": duration_ms,
                "Unit": "Milliseconds",
                "Dimensions": dimensions,
            },
        ],
    )
```

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

def log_delivery_attempt(delivery: IntegrationDelivery, response: httpx.Response):
    logger.info(
        "webhook_delivery",
        event_id=str(delivery.event_id),
        subscription_id=delivery.subscription_id,
        endpoint_id=delivery.subscription.endpoint_id,
        status_code=response.status_code,
        duration_ms=delivery.response_time_ms,
        attempt=delivery.attempts,
        correlation_id=delivery.event_data.get("correlation_id"),
    )
```

### Dashboards & Alerts

| Metric | Alert Threshold |
|--------|-----------------|
| Delivery success rate | < 95% over 15 min |
| P99 delivery latency | > 5s |
| DLQ depth | > 100 messages |
| Circuit breaker trips | > 3 per hour |

---

## Future Considerations

- **Delivery Dashboard UI**: Customer-facing UI for viewing delivery logs and retrying
- **Event Filtering DSL**: More expressive filters (greater than, contains, etc.)
- **Batch Delivery**: Combine multiple events into single webhook for high-volume scenarios
- **Native Slack App**: Rich Slack integration with interactive messages
