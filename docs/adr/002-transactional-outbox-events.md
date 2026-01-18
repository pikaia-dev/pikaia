# ADR 002: Transactional Outbox for Event-Driven Architecture

**Status:** Accepted
**Date:** January 18, 2026

## Context

We need a reliable way to publish domain events for:
- Audit logging (compliance, debugging)
- Customer webhooks (integrations with Zapier, Make, custom)
- Future microservices communication
- Analytics and reporting pipelines

The challenge: Publishing events must be **atomic with business operations**. If we save an order but fail to publish the "order.created" event, downstream systems are inconsistent.

Options considered:
1. **Publish directly in request** - Simple but loses events on failures
2. **Change Data Capture (CDC)** - Database-level, complex setup
3. **Transactional Outbox** - Store events in DB, publish asynchronously
4. **Event Sourcing** - Events as source of truth, major paradigm shift

## Decision

Use the **Transactional Outbox Pattern** with EventBridge as the event bus.

## Rationale

### Guaranteed Delivery
Events are stored in the same database transaction as business data:
```python
with transaction.atomic():
    order.save()
    publish_event("order.created", order, data={...})
    # Both succeed or both fail
```

No events are lost due to:
- Network failures to message broker
- Application crashes after save
- Message broker unavailability

### Decoupled Architecture
Business logic doesn't know about consumers:
- Same event feeds audit logs, webhooks, and analytics
- Add new consumers without changing publishers
- Events are self-describing with consistent schema

### Clean Separation of Concerns
```
Business Logic → OutboxEvent (DB) → Publisher Lambda → EventBridge
                                                          ↓
                                              ┌───────────┼───────────┐
                                              ↓           ↓           ↓
                                         Audit Log   Webhooks    Future Services
```

### Replay and Debugging
Events stored in database enable:
- Replaying events for new consumers
- Debugging production issues
- Audit trail of what happened and when

### Multi-Purpose Distribution
Single event publish, multiple consumers:
- **Audit Lambda** → Creates compliance audit log
- **Webhook Dispatcher** → Delivers to customer endpoints
- **Future**: Analytics, search indexing, notifications

## Consequences

### Positive
- **Data consistency** - Events always match business state
- **Reliability** - Events survive failures, retried automatically
- **Flexibility** - Add consumers without publisher changes
- **Debuggability** - Full event history in database
- **Scalability** - EventBridge handles fan-out

### Negative
- **Eventual consistency** - Events delivered async, not instant
- **Complexity** - More moving parts than direct calls
- **Storage** - Events accumulate in database (need cleanup policy)
- **Ordering** - Events may arrive out of order (design for idempotency)

### Mitigations
- Events published within seconds (Lambda polls every minute as fallback)
- Clear event schema with `event_id` for deduplication
- Database cleanup job for old published events
- Event consumers designed to be idempotent

## Implementation Notes

### Event Schema
```json
{
  "event_id": "uuid",
  "event_type": "member.invited",
  "occurred_at": "2024-01-15T10:30:00Z",
  "aggregate_type": "Member",
  "aggregate_id": "123",
  "organization_id": "org_456",
  "actor": {"id": "user_789", "type": "user"},
  "data": { ... },
  "correlation_id": "req_abc"
}
```

### Outbox Table
```python
class OutboxEvent(Model):
    event_id = UUIDField(unique=True)
    event_type = CharField()
    payload = JSONField()
    status = CharField()  # pending, published, failed
    attempts = IntegerField()
    next_attempt_at = DateTimeField()
```

### Publishing Flow
1. Business code calls `publish_event()` inside `transaction.atomic()`
2. OutboxEvent created with status="pending"
3. Lambda polls for pending events (every minute)
4. Lambda publishes batch to EventBridge
5. Lambda marks events as "published"
6. On failure: increment attempts, exponential backoff

### Consumer Pattern
All consumers must be idempotent:
```python
def handle_event(event):
    # Check if already processed
    if AuditLog.objects.filter(event_id=event["event_id"]).exists():
        return  # Already handled

    # Process event
    AuditLog.objects.create(event_id=event["event_id"], ...)
```
