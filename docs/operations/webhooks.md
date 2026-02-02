# Customer Webhooks

This document describes the customer-facing webhook system that allows organizations to receive real-time notifications when events occur in their account.

## Overview

Organizations can configure webhook endpoints to receive HTTP POST requests when specific events occur. This enables integrations with external systems, automation workflows, and real-time data synchronization.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Django App     │────▶│   EventBridge    │────▶│  Webhook Lambda │
│  (publishes     │     │   (pikaia-events) │     │  (dispatches)   │
│   events)       │     └──────────────────┘     └────────┬────────┘
└─────────────────┘                                       │
                                                          ▼
                                              ┌───────────────────────┐
                                              │  Customer Endpoints   │
                                              │  (org-configured URLs)│
                                              └───────────────────────┘
```

### Components

1. **Django Webhooks App** (`backend/apps/webhooks/`)
   - Models: `WebhookEndpoint`, `WebhookDelivery`
   - API: CRUD for endpoints, delivery logs, test sends
   - Event catalog: Single source of truth for available events

2. **EventBridge Consumer Lambda** (`infra/functions/webhook-dispatcher/`)
   - Triggered by EventBridge rules for webhook-eligible events
   - Looks up subscribed endpoints per organization
   - Dispatches HTTP requests with signatures

3. **CDK Infrastructure** (`infra/stacks/webhooks_stack.py`)
   - Lambda function with DLQ
   - EventBridge rules
   - CloudWatch alarms

## Event Catalog

Available events are defined in `backend/apps/webhooks/events.py` and exposed via API:

```
GET /api/v1/webhooks/events
```

### Member Events
- `member.created` - New member joined organization
- `member.updated` - Member profile updated
- `member.deleted` - Member removed from organization
- `member.role_changed` - Member role changed

### Organization Events
- `organization.updated` - Organization settings changed

### Billing Events
- `billing.subscription_created` - New subscription started
- `billing.subscription_updated` - Subscription changed
- `billing.subscription_canceled` - Subscription canceled
- `billing.payment_succeeded` - Payment processed successfully
- `billing.payment_failed` - Payment failed

## Payload Format

All webhook payloads follow this structure:

```json
{
  "id": "evt_01HN8KXYZ...",
  "spec_version": "1.0",
  "type": "member.created",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "organization_id": "org_01HN...",
  "data": {
    "member_id": "mbr_01HN...",
    "email": "jane@example.com",
    "name": "Jane Doe",
    "role": "member"
  }
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique event ID (use for idempotency) |
| `spec_version` | string | Payload schema version |
| `type` | string | Event type |
| `timestamp` | string | ISO 8601 timestamp |
| `organization_id` | string | Organization this event belongs to |
| `data` | object | Event-specific payload |

## Signature Verification

All webhook requests include a signature for verification:

### Headers

```
X-Webhook-ID: evt_01HN8KXYZ...
X-Webhook-Timestamp: 1705315800
X-Webhook-Signature: v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
```

### Verification Algorithm

```python
import hmac
import hashlib
import time

def verify_webhook(payload: bytes, headers: dict, secret: str) -> bool:
    """Verify webhook signature."""
    timestamp = headers.get('X-Webhook-Timestamp')
    signature = headers.get('X-Webhook-Signature')

    if not timestamp or not signature:
        return False

    # Check clock skew (5 minute window)
    current_time = int(time.time())
    if abs(current_time - int(timestamp)) > 300:
        return False

    # Construct signed payload
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"

    # Compute expected signature
    expected = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Extract signature value (remove 'v1=' prefix)
    provided = signature.split('=', 1)[1] if '=' in signature else signature

    return hmac.compare_digest(expected, provided)
```

### TypeScript Example

```typescript
import crypto from 'crypto';

function verifyWebhook(payload: string, headers: Headers, secret: string): boolean {
  const timestamp = headers.get('X-Webhook-Timestamp');
  const signature = headers.get('X-Webhook-Signature');

  if (!timestamp || !signature) return false;

  // Check clock skew (5 minute window)
  const currentTime = Math.floor(Date.now() / 1000);
  if (Math.abs(currentTime - parseInt(timestamp)) > 300) return false;

  // Construct signed payload
  const signedPayload = `${timestamp}.${payload}`;

  // Compute expected signature
  const expected = crypto
    .createHmac('sha256', secret)
    .update(signedPayload)
    .digest('hex');

  // Extract signature value
  const provided = signature.split('=')[1] || signature;

  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(provided));
}
```

## Response Handling

### Success

Return any `2xx` status code to acknowledge receipt. We recommend `200 OK` with an empty body or `{"received": true}`.

### Failure & Retries

Non-2xx responses or timeouts trigger retries with exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 1 minute |
| 3 | 5 minutes |
| 4 | 30 minutes |
| 5 | 2 hours |
| 6 (final) | 8 hours |

**Terminal states (no retry):**
- `410 Gone` - Endpoint permanently removed
- After 6 failed attempts - Endpoint marked as failing

### Idempotency

Your endpoint should be idempotent. Use the `X-Webhook-ID` header (same as `id` in payload) to deduplicate:

```python
def handle_webhook(request):
    event_id = request.headers.get('X-Webhook-ID')

    # Check if already processed
    if WebhookEvent.objects.filter(event_id=event_id).exists():
        return Response(status=200)  # Already processed, acknowledge

    # Process event...
    WebhookEvent.objects.create(event_id=event_id, processed_at=now())
    return Response(status=200)
```

## API Reference

### List Endpoints

```
GET /api/v1/webhooks/endpoints
```

Response:
```json
{
  "endpoints": [
    {
      "id": "wh_01HN...",
      "name": "Production Webhook",
      "description": "Sends events to our main integration",
      "url": "https://api.example.com/webhooks/pikaia",
      "events": ["member.created", "member.deleted"],
      "active": true,
      "last_delivery_status": "success",
      "last_delivery_at": "2024-01-15T10:30:00Z",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Create Endpoint

```
POST /api/v1/webhooks/endpoints
```

Request:
```json
{
  "name": "Production Webhook",
  "description": "Sends events to our main integration",
  "url": "https://api.example.com/webhooks/pikaia",
  "events": ["member.created", "member.deleted"]
}
```

Response:
```json
{
  "id": "wh_01HN...",
  "name": "Production Webhook",
  "url": "https://api.example.com/webhooks/pikaia",
  "events": ["member.created", "member.deleted"],
  "secret": "whsec_abc123...",
  "active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Note:** The `secret` is only returned on creation. Store it securely.

### Update Endpoint

```
PATCH /api/v1/webhooks/endpoints/{id}
```

Request:
```json
{
  "name": "Updated Name",
  "events": ["member.*"],
  "active": false
}
```

### Delete Endpoint

```
DELETE /api/v1/webhooks/endpoints/{id}
```

### Get Delivery Logs

```
GET /api/v1/webhooks/endpoints/{id}/deliveries
```

Response:
```json
{
  "deliveries": [
    {
      "id": "del_01HN...",
      "event_id": "evt_01HN...",
      "event_type": "member.created",
      "status": "success",
      "http_status": 200,
      "duration_ms": 245,
      "attempted_at": "2024-01-15T10:30:00Z",
      "response_snippet": "{\"received\": true}"
    }
  ]
}
```

### Send Test Event

```
POST /api/v1/webhooks/endpoints/{id}/test
```

Request:
```json
{
  "event_type": "member.created"
}
```

Response:
```json
{
  "success": true,
  "http_status": 200,
  "duration_ms": 156,
  "signature": "v1=5257a869...",
  "response_snippet": "{\"received\": true}"
}
```

### List Available Events

```
GET /api/v1/webhooks/events
```

Response:
```json
{
  "events": [
    {
      "type": "member.created",
      "description": "Triggered when a new member joins the organization",
      "category": "member",
      "payload_example": {
        "member_id": "mbr_01HN...",
        "email": "jane@example.com",
        "name": "Jane Doe",
        "role": "member"
      }
    }
  ]
}
```

---

## Infrastructure (CDK)

**Status: Pending Implementation**

The webhook consumer infrastructure needs to be added to the CDK stacks. This includes:

### Lambda Consumer
- Triggered by EventBridge rules for webhook-eligible events
- Filters: `member.*`, `organization.*`, `billing.*`
- Calls Django API to look up subscribed endpoints
- Dispatches webhooks via the WebhookDispatcher service

### Dead Letter Queue (DLQ)
- SQS queue for failed webhook dispatches
- Alarm when DLQ depth > 0

### CloudWatch Alarms
- `WebhookDeliverySuccess` metric
- `WebhookDeliveryFailure` metric
- `WebhookDeliveryLatency` metric (P95)
- Alarm on sustained failure rate > 10%

### EventBridge Rules
```python
# Filter for webhook-eligible events
Rule(
    event_pattern={
        "source": ["pikaia"],
        "detail-type": [
            {"prefix": "member."},
            {"prefix": "organization."},
            {"prefix": "billing."},
        ]
    }
)
```

The infrastructure will be gated behind `ENABLE_WEBHOOKS=true` in CDK context.

---

## V2 Roadmap (Planned Features)

The following features are planned for future releases:

### Secret Rotation (High Priority)

**Why deferred:** Requires careful UX design for dual-secret overlap window.

**Planned implementation:**
- `POST /api/v1/webhooks/endpoints/{id}/rotate-secret`
- Returns new secret while keeping old secret valid for 24 hours
- Both signatures sent during overlap: `X-Webhook-Signature: v1=new...,v1=old...`
- Consumer verifies against either signature during migration

### URL Verification

**Why deferred:** Not critical for initial launch; trusted customers.

**Planned implementation:**
- On endpoint creation, send verification challenge
- Endpoint must respond with challenge token
- `verification_status`: `pending`, `verified`, `failed`
- Only verified endpoints receive events (optional enforcement)

### Advanced Filtering

**Why deferred:** Current wildcard matching (e.g., `member.*`) covers most cases.

**Planned implementation:**
- Filter by payload fields: `{"data.role": "admin"}`
- Conditional delivery based on event content

### Svix Integration

**Why deferred:** Direct HTTP delivery is sufficient for V1; Svix adds complexity.

**Planned implementation when `ENABLE_SVIX=true`:**
- Svix handles signing (we provide the secret to Svix)
- Store Svix endpoint IDs in `WebhookEndpoint.svix_endpoint_id`
- Svix manages retries, delivery logs
- Our API proxies to Svix for consistency
- Rotation: Call Svix API to update secret

See `docs/SVIX_INTEGRATION.md` for detailed setup (to be created).

---

## Observability

### Metrics (CloudWatch)

- `WebhookDeliverySuccess` - Count of successful deliveries
- `WebhookDeliveryFailure` - Count of failed deliveries
- `WebhookDeliveryLatency` - P50/P95/P99 delivery duration

### Alarms

- Sustained failure rate > 10% for 5 minutes
- DLQ message count > 0

### Debugging

Check delivery logs via API or directly in database:
- `WebhookDelivery.error_type`: `timeout`, `connection_error`, `http_error`, `invalid_response`
- `WebhookDelivery.response_snippet`: First 500 chars of response (no PII)
