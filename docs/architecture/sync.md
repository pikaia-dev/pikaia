# Sync Architecture

This document defines the offline-first sync engine design for mobile and desktop applications.

## Table of Contents

- [Overview](#overview)
- [Design Principles](#design-principles)
- [Sync Protocol](#sync-protocol)
- [Data Model](#data-model)
- [Conflict Resolution](#conflict-resolution)
- [Client Implementation](#client-implementation)
- [Scale Considerations](#scale-considerations)

---

## Overview

The sync engine enables mobile and desktop apps to work offline while maintaining data consistency with the server. The web frontend uses standard REST APIs and does not require sync.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                 │
├─────────────────────┬─────────────────────┬─────────────────────┤
│   Web (React)       │   Mobile (RN/       │   Desktop           │
│                     │   Flutter)          │   (Electron)        │
│   Always online     │   Offline-first     │   Offline-first     │
│   Standard REST     │   Sync Engine       │   Sync Engine       │
│   /api/v1/*         │   /api/v1/sync/*    │   /api/v1/sync/*    │
└─────────┬───────────┴──────────┬──────────┴────────┬────────────┘
          │                      │                   │
          │                      ▼                   │
          │              ┌───────────────┐           │
          │              │   Django API   │◀──────────┘
          │              │ (single sync   │
          └─────────────▶│  endpoint)     │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  PostgreSQL   │
                         │ (source of    │
                         │   truth)      │
                         └───────────────┘
```

### Why Django, Not Direct EventBridge

| Concern | Django in Path | Direct to EventBridge |
|---------|----------------|----------------------|
| **Auth** | Stytch JWT (exists) | Lambda authorizer (new) |
| **Validation** | Immediate rejection | Async rejection (complex) |
| **Sync endpoints** | Push + Pull unified | Two systems |
| **Scale** | 5,000+ req/s per container | Infinite (but more complex) |

For B2B SaaS with 1,000-10,000 companies, Django handles the load comfortably. See [Scale Considerations](#scale-considerations) for escape hatch.

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Local-first** | Client writes to local DB, UI reflects local state |
| **Server as truth** | PostgreSQL is authoritative for queries |
| **Client-generated IDs** | UUIDv7 for time-ordered uniqueness |
| **Intent over state** | Operations describe intent, not raw diffs |
| **Idempotency** | Every operation has a unique key |
| **At-least-once** | Assume duplicates, handle gracefully |
| **Soft deletes** | Tombstones for deletion propagation |

---

## Sync Protocol

### Overview

Two endpoints handle all sync operations:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/sync/push` | POST | Client sends local changes to server |
| `/api/v1/sync/pull` | GET | Client fetches server changes |

### Push: Client → Server

**Request:**

```json
POST /api/v1/sync/push
Authorization: Bearer <jwt>

{
  "operations": [
    {
      "idempotency_key": "op_01HN8J9K2M3N4P5Q6R7S8T9U0V",
      "entity_type": "time_entry",
      "entity_id": "te_01HN8J9K2M3N4P5Q6R7S8T9U0V",
      "intent": "create",
      "timestamp": "2025-01-02T23:00:00Z",
      "data": {
        "description": "Working on feature X",
        "project_id": "prj_01HN...",
        "started_at": "2025-01-02T22:00:00Z",
        "ended_at": "2025-01-02T23:00:00Z"
      }
    },
    {
      "idempotency_key": "op_01HN8J9K2M3N4P5Q6R7S8T9U1W",
      "entity_type": "time_entry",
      "entity_id": "te_01HN8J9K2M3N4P5Q6R7S8T9U0V",
      "intent": "update",
      "timestamp": "2025-01-02T23:05:00Z",
      "data": {
        "description": "Working on feature X (updated)"
      }
    }
  ]
}
```

**Response:**

```json
{
  "results": [
    {
      "idempotency_key": "op_01HN8J9K2M3N4P5Q6R7S8T9U0V",
      "status": "applied",
      "server_timestamp": "2025-01-02T23:00:01Z"
    },
    {
      "idempotency_key": "op_01HN8J9K2M3N4P5Q6R7S8T9U1W",
      "status": "applied",
      "server_timestamp": "2025-01-02T23:05:01Z"
    }
  ]
}
```

**Error Response:**

```json
{
  "results": [
    {
      "idempotency_key": "op_01HN8J9K...",
      "status": "rejected",
      "error_code": "PROJECT_ARCHIVED",
      "error_message": "Cannot track time to archived project"
    }
  ]
}
```

### Pull: Server → Client

**Request:**

```
GET /api/v1/sync/pull?since=<cursor>&entity_types=time_entry,project&limit=100
Authorization: Bearer <jwt>
```

**Response:**

```json
{
  "changes": [
    {
      "entity_type": "time_entry",
      "entity_id": "te_01HN8J9K2M3N4P5Q6R7S8T9U0V",
      "operation": "upsert",
      "data": {
        "description": "Working on feature X (updated)",
        "project_id": "prj_01HN...",
        "started_at": "2025-01-02T22:00:00Z",
        "ended_at": "2025-01-02T23:00:00Z"
      },
      "updated_at": "2025-01-02T23:05:01Z"
    },
    {
      "entity_type": "time_entry",
      "entity_id": "te_01HN8J9K2M3N4P5Q6R7S8DELETED",
      "operation": "delete",
      "updated_at": "2025-01-02T23:10:00Z"
    }
  ],
  "cursor": "2025-01-02T23:10:00Z_te_01HN8J9K...",
  "has_more": false
}
```

### Cursor Design

The cursor is an opaque token encoding position in the changeset:

```
{timestamp}_{entity_id}
```

**Why timestamp + ID?**
- Timestamp alone is ambiguous (multiple changes per millisecond)
- Combined value ensures stable ordering
- Opaque to client—can change encoding without breaking clients

**Monotonicity Guarantees:**

> [!IMPORTANT]
> The cursor must be monotonic from the database, not client clocks. Use `server_timestamp` (assigned on write) as the primary cursor component.

```python
# Pull query: Pin to snapshot semantics
def get_changes_since(workspace_id: str, cursor: str, limit: int = 100):
    """
    Fetch changes since cursor with snapshot consistency.
    """
    cursor_ts, cursor_id = parse_cursor(cursor)
    
    # Use server-assigned updated_at, not client timestamp
    # Composite index: (workspace, updated_at, id) ensures monotonic ordering
    changes = (
        SyncableModel.objects
        .filter(workspace_id=workspace_id)
        .filter(
            Q(updated_at__gt=cursor_ts) |
            Q(updated_at=cursor_ts, id__gt=cursor_id)
        )
        .order_by("updated_at", "id")
        [:limit]
    )
    
    return changes
```

**Required Index:**

```python
class Meta:
    indexes = [
        # Composite index for cursor pagination
        models.Index(fields=["workspace", "updated_at", "id"]),
    ]
```

### Operation Intents

| Intent | Meaning |
|--------|---------|
| `create` | New entity |
| `update` | Modify existing (partial data allowed) |
| `delete` | Mark as deleted (tombstone) |

---

## Data Model

### Server-Side Models

#### SyncOperation (Incoming Operations Log)

```python
class SyncOperation(models.Model):
    """
    Stores incoming operations for idempotency and debugging.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    idempotency_key = models.CharField(max_length=100, unique=True)
    
    workspace = models.ForeignKey(Organization, on_delete=models.CASCADE)
    actor = models.ForeignKey(Member, on_delete=models.CASCADE)
    
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=100)
    intent = models.CharField(max_length=20)  # create, update, delete
    
    payload = models.JSONField()
    client_timestamp = models.DateTimeField()
    server_timestamp = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(max_length=20)  # applied, rejected, duplicate
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["workspace", "server_timestamp"]),
            models.Index(fields=["idempotency_key"]),
        ]
```

#### Sync-Enabled Entity Pattern

All entities that participate in sync must have:

```python
class SyncableModel(models.Model):
    """
    Abstract base for sync-enabled entities.
    """
    id = models.CharField(
        max_length=50,
        primary_key=True,
        default=generate_prefixed_uuid  # e.g., "te_01HN..."
    )
    
    workspace = models.ForeignKey(Organization, on_delete=models.CASCADE)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # Soft delete
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["workspace", "updated_at"]),
        ]
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
```

### Client-Side (Conceptual)

Client apps maintain:

| Collection | Purpose |
|------------|---------|
| Entities (local DB) | SQLite/Realm with entity data |
| Pending Operations | Queue of unsynced operations |
| Sync Cursor | Last successful pull cursor |

---

## Conflict Resolution

### Strategy Per Entity Type

| Entity | Strategy | Rationale |
|--------|----------|-----------|
| `time_entry` | Last-write-wins (server timestamp) | Simple, acceptable for time tracking |
| `note` | Field-level merge | Preserve concurrent edits to different fields |
| `contact` | Manual merge (if conflict) | High-value data, user decides |

### Last-Write-Wins (LWW)

Default for most entities:

```python
def apply_operation(op: SyncOperation, entity: SyncableModel):
    """Apply operation using LWW based on server timestamp."""
    
    if entity.updated_at > op.server_timestamp:
        # Server already has newer data
        return "skipped"
    
    for field, value in op.payload.items():
        setattr(entity, field, value)
    
    entity.updated_at = op.server_timestamp
    entity.save()
    return "applied"
```

### Field-Level Merge

For text-heavy entities like notes:

```python
def merge_fields(existing: dict, incoming: dict, base: dict) -> dict:
    """
    Three-way merge at field level.
    
    - If only one side changed, take that change
    - If both changed to same value, no conflict
    - If both changed to different values, incoming wins (LWW fallback)
    """
    result = {}
    for field in set(existing.keys()) | set(incoming.keys()):
        existing_val = existing.get(field)
        incoming_val = incoming.get(field)
        base_val = base.get(field)
        
        if existing_val == incoming_val:
            result[field] = existing_val
        elif existing_val == base_val:
            # Only incoming changed
            result[field] = incoming_val
        elif incoming_val == base_val:
            # Only existing changed
            result[field] = existing_val
        else:
            # Both changed → LWW fallback
            result[field] = incoming_val
    
    return result
```

### Tombstone Lifecycle

1. Client sends `delete` intent
2. Server sets `deleted_at` (soft delete)
3. Deleted entities included in `pull` responses with `operation: "delete"`
4. Client removes from local DB
5. Server hard-deletes after 90 days (cleanup job)

---

## Client Implementation

### Recommended Architecture (React Native/Flutter)

```
┌─────────────────────────────────────────────────┐
│                    UI Layer                      │
│            (React components / Widgets)          │
├─────────────────────────────────────────────────┤
│               State Management                   │
│    (MobX / Riverpod / Zustand + local queries)   │
├─────────────────────────────────────────────────┤
│                 Sync Engine                      │
│     ┌─────────────┬─────────────┬────────────┐  │
│     │ Operation   │ Sync        │ Conflict   │  │
│     │ Queue       │ Scheduler   │ Resolver   │  │
│     └─────────────┴─────────────┴────────────┘  │
├─────────────────────────────────────────────────┤
│               Local Database                     │
│         (SQLite / Realm / WatermelonDB)          │
└─────────────────────────────────────────────────┘
```

### Client-Side ID Generation

Use **UUIDv7** for time-ordered, collision-resistant IDs:

```typescript
// Using uuid v7 for client-generated IDs
import { v7 as uuidv7 } from 'uuid';

const PREFIX_MAP = {
  time_entry: 'te_',
  project: 'prj_',
  contact: 'ct_',
};

function generateId(entityType: string): string {
  const prefix = PREFIX_MAP[entityType] || 'ent_';
  return `${prefix}${uuidv7()}`;
}
```

### Sync Scheduler

```typescript
class SyncScheduler {
  private pendingQueue: Operation[] = [];
  private lastCursor: string | null = null;
  
  async sync() {
    // 1. Push pending operations
    if (this.pendingQueue.length > 0) {
      const results = await api.push(this.pendingQueue);
      this.handlePushResults(results);
    }
    
    // 2. Pull server changes
    const { changes, cursor, hasMore } = await api.pull(this.lastCursor);
    this.applyServerChanges(changes);
    this.lastCursor = cursor;
    
    // 3. Continue if more data
    if (hasMore) {
      await this.sync();
    }
  }
  
  private handlePushResults(results: OperationResult[]) {
    for (const result of results) {
      if (result.status === 'applied' || result.status === 'duplicate') {
        this.removeFromQueue(result.idempotency_key);
      } else if (result.status === 'rejected') {
        this.markOperationFailed(result);
      }
    }
  }
}
```

---

## Scale Considerations

### Current Design Capacity

| Metric | Estimate |
|--------|----------|
| Companies per app | 1,000 - 10,000 |
| Users per company (avg) | 10 - 50 |
| Concurrent syncing users | ~1,000 - 5,000 |
| Sync frequency | Every 30s - 5min |
| Requests per second | ~100 - 500 |

Django on ECS Fargate handles this comfortably.

### Escape Hatch: High-Scale Ingestion

If you need >10,000 concurrent syncing users:

```
Before:  Mobile → Django → PostgreSQL → EventBridge

After:   Mobile → API Gateway → Lambda → PostgreSQL → EventBridge
                 (swap ingestion layer)
```

**Migration steps:**
1. Keep sync protocol identical
2. Move validation to Lambda
3. Use API Gateway Lambda authorizer with Stytch
4. Django becomes read-only for sync-eligible entities

### Database Indexing

Critical indexes for sync performance:

```python
class Meta:
    indexes = [
        # Pull query: changes since cursor
        models.Index(fields=["workspace", "updated_at"]),
        
        # Idempotency check
        models.Index(fields=["idempotency_key"]),
        
        # Soft delete cleanup
        models.Index(fields=["deleted_at"]),
    ]
```

### Rate Limiting

Implement per-workspace rate limiting:

```python
# Django middleware or decorator
@rate_limit(key="workspace:{workspace_id}", limit=100, period=60)
def sync_push(request):
    ...
```

---

## Compression & Batching

### Response Compression

Enable gzip for sync responses to reduce bandwidth on mobile:

```python
# Django middleware (or nginx/ALB config)
MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    ...
]

# Or in nginx
location /api/v1/sync/ {
    gzip on;
    gzip_types application/json;
    gzip_min_length 1000;
}
```

### Request Batching

Clients should batch operations in push requests:

```typescript
class SyncScheduler {
  private readonly BATCH_SIZE = 50;
  private readonly BATCH_DELAY_MS = 100;
  
  async pushWithBatching(operations: Operation[]) {
    // Batch operations to reduce round-trips
    for (let i = 0; i < operations.length; i += this.BATCH_SIZE) {
      const batch = operations.slice(i, i + this.BATCH_SIZE);
      await api.push(batch);
    }
  }
}
```

### Payload Size Limits

| Config | Value | Rationale |
|--------|-------|-----------|
| Max operations per push | 100 | Prevent timeout |
| Max payload size | 1MB | Mobile-friendly |
| Max changes per pull | 500 | Pagination |

---

## Background Notifications

Reduce polling when online by notifying clients of server changes:

### Push Notification Flow

```
Server Change → EventBridge → SNS → Mobile Push → Client pulls
```

### Implementation Options

| Option | Latency | Complexity | Use Case |
|--------|---------|------------|----------|
| Polling | 30s-5min | Low | Default |
| SNS Push | <1s | Medium | Mobile (iOS/Android) |
| WebSocket | <100ms | High | Desktop, always-on clients |
| SSE | <100ms | Medium | Web fallback |

### SNS Nudge Pattern

```python
# Lambda: Send push notification on sync-relevant events
def notify_client_to_sync(event, context):
    """
    Send silent push notification to trigger client sync.
    """
    workspace_id = event["detail"]["workspace_id"]
    
    # Get device tokens for workspace members
    tokens = get_device_tokens_for_workspace(workspace_id)
    
    for token in tokens:
        sns.publish(
            TargetArn=token.sns_endpoint_arn,
            Message=json.dumps({"type": "sync_nudge"}),
            MessageAttributes={
                "AWS.SNS.MOBILE.APNS.PUSH_TYPE": {
                    "DataType": "String",
                    "StringValue": "background",
                },
            },
        )
```

---

## Future Considerations

- **Selective Sync**: Allow clients to sync only specific entity types or date ranges
- **Partial Sync Recovery**: Resume interrupted syncs without re-fetching
- **Conflict UI Components**: Reusable UI for manual conflict resolution
