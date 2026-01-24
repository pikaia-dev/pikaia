# Sync Engine

This document defines the offline-first sync engine for mobile and desktop applications.

## Table of Contents

- [Overview](#overview)
- [Architecture Philosophy](#architecture-philosophy)
- [Core Data Models](#core-data-models)
- [Sync Protocol](#sync-protocol)
- [Conflict Resolution Strategies](#conflict-resolution-strategies)
- [Client-Side Architecture](#client-side-architecture)
- [Example Use Cases](#example-use-cases)
- [Integration with Existing Infrastructure](#integration-with-existing-infrastructure)
- [Scalability Considerations](#scalability-considerations)
- [Full Re-Sync Triggers](#full-re-sync-triggers)
- [Error Codes](#error-codes)
- [Schema Changes and Versioning](#schema-changes-and-versioning)
- [Failed Operations Handling](#failed-operations-handling)
- [Compression and Batching](#compression-and-batching)
- [Background Notifications](#background-notifications)
- [Testing Strategy](#testing-strategy)
- [Key Design Decisions](#key-design-decisions)

---

## Overview

The sync engine enables mobile and desktop apps to work offline while maintaining data consistency with the server. The web frontend uses standard REST APIs and does not require sync.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                 │
├─────────────────────┬─────────────────────┬─────────────────────┤
│   Web (React)       │   Mobile (Native)   │   Desktop (Native)  │
│                     │                     │                     │
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

### Existing Foundations

Pikaia already has the foundations for a sync engine:
- Transactional outbox pattern (`OutboxEvent`)
- Webhook delivery with retry and circuit breaker
- Soft-delete pattern across models
- Device linking infrastructure
- Multi-tenant isolation

### Why Django, Not Direct EventBridge

| Concern | Django in Path | Direct to EventBridge |
|---------|----------------|----------------------|
| **Auth** | Stytch JWT (exists) | Lambda authorizer (new) |
| **Validation** | Immediate rejection | Async rejection (complex) |
| **Sync endpoints** | Push + Pull unified | Two systems |
| **Scale** | 5,000+ req/s per container | Infinite (but more complex) |

For B2B SaaS with 1,000-10,000 companies, Django handles the load comfortably. See [Scalability Considerations](#scalability-considerations) for escape hatch.

---

## Architecture Philosophy

### Local-First, Server-Authoritative Hybrid

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Mobile/Desktop)                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   SQLite    │◄──►│ Sync Engine │◄──►│ Pending Op Queue    │  │
│  │   (SSOT)    │    │   Worker    │    │ (survives crashes)  │  │
│  └─────────────┘    └──────┬──────┘    └─────────────────────┘  │
└────────────────────────────┼────────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────┼────────────────────────────────────┐
│                        SERVER (Pikaia)                          │
│  ┌─────────────┐    ┌──────┴──────┐    ┌─────────────────────┐  │
│  │   Sync API  │───►│  Conflict   │───►│   OutboxEvent       │  │
│  │  /push /pull│    │  Resolver   │    │   (existing)        │  │
│  └─────────────┘    └─────────────┘    └──────────┬──────────┘  │
│                                                    │             │
│  ┌─────────────────────────────────────────────────┼───────────┐│
│  │                    PostgreSQL                               ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  ││
│  │  │SyncOperation│  │  Entities   │  │    WebhookDelivery  │  ││
│  │  │   (log)     │  │ (syncable)  │  │      (existing)     │  ││
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

The local database is the single source of truth for the client. The server is authoritative for conflict resolution and final state.

### Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Local-first** | Client writes to local DB, UI reflects local state |
| **Server as truth** | PostgreSQL is authoritative for queries |
| **Client-generated IDs** | ULIDs for time-ordered uniqueness |
| **Intent over state** | Operations describe intent, not raw diffs |
| **Idempotency** | Every operation has a unique key |
| **At-least-once** | Assume duplicates, handle gracefully |
| **Soft deletes** | Tombstones for deletion propagation |

#### 1. Stale-Read Tolerant

Clients often have old data. That's expected and fine.

- Clients can push changes without being fully up-to-date first
- Updates are field-level patches (only changed fields are sent)
- Server resolves conflicts using the configured strategy (LWW, merge, etc.)
- Things may be temporarily inconsistent, but they converge eventually

#### 2. PATCH Semantics for Updates

For `update` operations, `data` contains only the changed fields:

```python
# Client sends only what changed
{
    "intent": "update",
    "entity_id": "ct_01HN8J...",
    "data": {"phone": "+1-555-1234"}  # Only phone changed
}

# Server behavior:
# - Updates the phone field
# - Keeps all other fields (name, email, company) unchanged
# - Does NOT null out omitted fields
```

Server implementation must:
- Only update fields present in `data`
- Preserve existing values for omitted fields
- Track field-level timestamps if using field-level LWW

#### 3. Empty Queue Does Not Mean Up-to-Date

An empty local operation queue means "no local changes to push." That's it.

It does not mean:
- Client has received all server changes
- Client state matches server state
- No pull is needed

```swift
// Wrong assumption
if await operationQueue.isEmpty {
    print("Client is in sync")  // False!
}

// Correct understanding
if await operationQueue.isEmpty {
    print("No pending local changes")
    // Still need to pull to get server changes
}
```

#### 4. Server-Side Mutations Must Enter Sync Stream

Any server-side mutation that should be reflected on clients must update `updated_at`. Otherwise, clients will never see the change.

| Mutation Source | Must Update `updated_at`? | Example |
|-----------------|---------------------------|---------|
| Client push | Yes (automatic via `save()`) | User edits contact |
| Admin panel | Yes | Admin fixes data |
| Background job | Yes | Scheduled cleanup |
| Cron task | Yes | Nightly recalculation |
| Database trigger | Yes | Denormalization |
| Webhook handler | Yes | External integration |

```python
# Wrong: Direct update bypasses updated_at
Contact.objects.filter(id=contact_id).update(status='archived')

# Correct: Use save() or explicit updated_at
contact = Contact.objects.get(id=contact_id)
contact.status = 'archived'
contact.save()  # updated_at set automatically

# Or with bulk update:
Contact.objects.filter(id=contact_id).update(
    status='archived',
    updated_at=timezone.now(),  # Explicit
)
```

#### 5. Trade-off: Patch Updates + Eventual Consistency

With field-level patches and stale-read tolerance:

| Scenario | Behavior | Acceptable? |
|----------|----------|-------------|
| Client A and B both update different fields | Both changes merge | Yes |
| Client A updates field X, server job updates field X | LWW resolves | Yes |
| Client pulls, server updates entity, client pushes stale patch | Client's field wins (LWW) | Intentional |

This is acceptable when:
- Field-level LWW is the configured strategy
- "Last writer wins" is intentional policy
- Business logic doesn't require strict ordering

Requires additional business logic for:
- Inventory counts
- Financial balances
- Any domain with constraints that can be violated by concurrent offline writes

LWW sync does not lose data in these cases. All operations are recorded. The question is how to handle constraint violations after sync:

```
Example: Inventory over-commitment

Stock: 5 units
Client A (offline): Sells 3 → records sale of 3
Client B (offline): Sells 4 → records sale of 4
Both sync: 7 units sold from 5 available

Sync engine's job: Record both sales accurately
Business logic's job: Decide what to do
  - Backorder 2 units
  - Cancel later order + notify customer
  - Allow negative stock (common in B2B)
  - Flag for manual review
```

This is a policy decision, not a sync failure. The sync engine captures intent; business rules handle reconciliation.

Use CRDTs for:
- Collaborative text editing (character-level convergence)
- Counters that must converge (G-Counter, PN-Counter)
- Sets with add/remove semantics (OR-Set)

---

## Core Data Models

> **Implementation**: See [`apps/sync/models.py`](../../backend/apps/sync/models.py)

### Syncable Entity Base

Entities that participate in sync inherit from `SyncableModel`:

| Field | Purpose |
|-------|---------|
| `id` | ULID with entity-type prefix (e.g., `ct_01HN8J...`) |
| `organization` | Tenant isolation |
| `sync_version` | Lamport clock, increments on every save |
| `last_modified_by` | Actor tracking |
| `device_id` | Origin device for debugging |

Key behaviors:
- Inherits `SoftDeleteMixin` for tombstone support
- Uses `.all_objects` manager to include deleted records in sync queries
- Indexed on `(organization, updated_at, id)` for efficient cursor-based pulls

### Sync Operation Log (Inbound)

The `SyncOperation` model is an append-only log of all sync operations for audit and replay.

| Field | Purpose |
|-------|---------|
| `idempotency_key` | Unique key for duplicate detection |
| `intent` | `create`, `update`, or `delete` |
| `status` | `pending`, `applied`, `rejected`, `conflict`, `duplicate` |
| `drift_ms` | Clock drift between client and server (observability) |
| `conflict_fields` | Fields rejected by LWW (observability) |

#### Observability: Per-Operation Metrics

Since every push writes to `SyncOperation`, we get per-operation metrics for free:

| Metric | Field | What it tells you | Normal | Warning |
|--------|-------|-------------------|--------|---------|
| Drift | `drift_ms` | Client clock offset | < 1s | > 5s |
| Conflicts | `conflict_fields` | Fields rejected by LWW | < 5% | > 20% |
| Retries | `client_retry_count` | Network reliability | < 0.5 | > 2 |

See [`apps/sync/services.py:process_sync_operation`](../../backend/apps/sync/services.py) for metric collection.

### Field-Level Timestamps for LWW

> **Implementation**: See [`FieldLevelLWWMixin`](../../backend/apps/sync/models.py) and [`apply_field_level_lww`](../../backend/apps/sync/services.py)

Field-level LWW tracks when each field was last modified, enabling granular merge when different clients edit different fields.

**Storage**: `field_timestamps` JSON field maps field names to ISO timestamps:
```json
{"name": "2025-01-23T10:00:00Z", "phone": "2025-01-23T09:30:00Z"}
```

**Resolution logic**:
1. Client wins if server has no timestamp for the field (new/migrated)
2. Client wins if `client_timestamp > server_field_timestamp`
3. Otherwise server wins, field is added to `conflict_fields` for observability

**Migration**: Run `python manage.py backfill_field_timestamps` to initialize existing records. By default, missing timestamps are treated as "infinitely old" (client always wins).

#### When to Use Field-Level vs Entity-Level LWW

| Scenario | Recommendation |
|----------|----------------|
| Simple entities (tags, labels) | Entity-level LWW (simpler) |
| Entities with independent fields (contacts) | Field-level LWW |
| Entities where fields are related (address) | Entity-level or grouped |
| High-conflict entities | Consider CRDT or manual resolution |

---

## Sync Protocol

> **Implementation**: See [`apps/sync/api.py`](../../backend/apps/sync/api.py) and [`apps/sync/schemas.py`](../../backend/apps/sync/schemas.py)

### Overview

Two endpoints handle all sync operations:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/sync/push` | POST | Client sends local changes to server |
| `/api/v1/sync/pull` | GET | Client fetches server changes |

### Sync Cycle Sequence

```
Client                           Server
  │                                 │
  │──── POST /sync/push ───────────►│
  │     {operations: [...]}         │
  │                                 │ For each operation:
  │                                 │ ├─ Check idempotency_key
  │                                 │ ├─ Apply LWW resolution
  │                                 │ └─ Log to SyncOperation
  │◄──── {results: [...]} ──────────│
  │                                 │
  │──── GET /sync/pull?since=X ────►│
  │                                 │ Query all_objects (includes deleted)
  │                                 │ Filter by cursor
  │◄──── {changes, cursor} ─────────│
  │                                 │
  │     [Apply changes locally]     │
  │     [Persist new cursor]        │
  │                                 │
```

### Soft-Delete Semantics in Sync

The existing `SoftDeleteMixin` pattern requires careful handling in sync operations.

#### The Problem

```python
# Default manager excludes deleted records
Contact.objects.filter(updated_at__gt=cursor)  # Misses deletions!

# all_objects includes everything
Contact.all_objects.filter(updated_at__gt=cursor)  # Includes deletions
```

#### The Solution

1. Pull queries must use `.all_objects` to include soft-deleted records
2. Existing `soft_delete()` already updates `updated_at` (see `core/models.py:158`), so deletions appear in cursor-based queries
3. Return `operation: 'delete'` for records where `deleted_at IS NOT NULL`
4. Tombstone retention: Keep deleted records for 90 days before hard-delete (allows late-syncing clients to receive deletions)

#### Implementation

See [`fetch_changes_for_pull`](../../backend/apps/sync/services.py) - key points:
- Uses `all_objects` manager to include soft-deleted records
- Deleted records return `operation: 'delete'` with no data payload
- Orders by `(updated_at, id)` for stable cursor-based pagination

#### Tombstone Cleanup

Run periodically to hard-delete old tombstones:

```bash
python manage.py cleanup_tombstones --retention-days=90
```

Retention period should exceed the longest expected client offline duration.

#### Client Handling of Deletions

```swift
// SyncEngine+Pull.swift

func processPullResponse(_ response: SyncPullResponse, context: ModelContext) async throws {
    for change in response.changes {
        if change.operation == "delete" {
            // Remove from local database
            try deleteEntity(type: change.entityType, id: change.entityId, context: context)
            // Also remove any pending operations for this entity
            try await operationQueue.removeForEntity(type: change.entityType, id: change.entityId)
        } else {
            // Upsert: insert or update
            try upsertEntity(type: change.entityType, id: change.entityId, data: change.data, context: context)
        }
    }
    try context.save()

    // Persist new cursor
    await cursorManager.setCursor(response.cursor)
}
```

### Cursor Ordering and Clock Skew

With multiple Django instances (ECS tasks), clock skew can cause missed records.

```
Timeline (wall clock):  ─────────────────────────────────────────►

Server A (clock +50ms fast):  Saves entity X at "10:00:00.150"
Server B (clock -50ms slow):            Saves entity Y at "10:00:00.050"
                                        (actually happened AFTER X)

Client pulls with cursor "10:00:00.150"
→ Entity Y (timestamp "10:00:00.050") is NEVER returned
→ Client permanently misses entity Y
```

#### Server Timestamps vs Client Timestamps

The cursor must use server-controlled values, never client-supplied timestamps:

| Field | Source | Used For |
|-------|--------|----------|
| `updated_at` | Server (`auto_now=True`) | Cursor - ordering pull results |
| `sync_version` | Server (incremented on save) | Cursor (alternative) - guaranteed ordering |
| `client_timestamp` | Client | Conflict resolution only (not for cursor) |

```python
# In push handler:
operation.client_timestamp  # Used for LWW conflict resolution
entity.updated_at           # Set by server, used for cursor/pull ordering

# These are different timestamps with different purposes:
# - client_timestamp: "when did the user make this change?" (for LWW)
# - updated_at: "when did the server persist this?" (for cursor)
```

Why this matters: If the cursor used `client_timestamp`:
- Clients with wrong clocks could corrupt ordering
- Malicious clients could manipulate sync order
- Clock drift would cause missed records

#### Design Decisions

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| Primary cursor field | `updated_at` (server-set via `auto_now`) | Simple, server-controlled, works 99%+ with NTP |
| Tiebreaker | `id` (ULID) | Deterministic ordering for same-timestamp records |
| Clock skew mitigation | Overlap window | Catches records from slightly-behind server clocks |
| High-consistency option | `sync_sequence_id` | Optional, database sequence for guaranteed ordering |
| NOT used for cursor | `client_timestamp` | Only for LWW conflict resolution |

#### Solution: Overlap Window

Pull queries go back slightly from the cursor (100ms) to catch clock-skewed records. Clients handle duplicates via version comparison - only apply if `change.version > local.version`.

#### Optional: Monotonic Sequence

For high-consistency use cases (financial transactions), use a database sequence instead of `updated_at`:

```sql
CREATE SEQUENCE sync_global_seq;
-- Trigger assigns nextval on insert/update
```

#### Periodic Full Sync

Even with overlap windows, clients should do a full resync every 24 hours as a safety net. See [Full Re-Sync Triggers](#full-re-sync-triggers).

#### Summary: When to Use Which Approach

| Scenario | Recommended Cursor | Notes |
|----------|-------------------|-------|
| Most B2B apps | `updated_at` + overlap | Simple, handles 99.9% of cases |
| High-write frequency | `updated_at` + overlap + periodic full sync | Safety net for edge cases |
| Financial/audit-critical | `sync_sequence_id` | Guaranteed ordering, slight perf cost |
| Collaborative editing | CRDT (no cursor needed) | Convergence is automatic |

### Push Endpoint (Client → Server)

**Endpoint**: `POST /api/v1/sync/push`

**Request fields**:
| Field | Required | Description |
|-------|----------|-------------|
| `idempotency_key` | Yes | Client-generated unique key (survives retries) |
| `entity_type` | Yes | Registered entity type (e.g., `contact`) |
| `entity_id` | Yes | ULID of the entity |
| `intent` | Yes | `create`, `update`, or `delete` |
| `client_timestamp` | Yes | When the client made this change (for LWW) |
| `data` | Yes | Entity data (PATCH semantics for updates) |
| `base_version` | No | For optimistic concurrency checks |

**Response fields**:
| Field | Description |
|-------|-------------|
| `status` | `applied`, `rejected`, `conflict`, or `duplicate` |
| `server_timestamp` | When server processed the operation |
| `error_code` | Error identifier (if rejected) |
| `error_message` | Human-readable error (if rejected) |

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
      "client_timestamp": "2025-01-02T23:00:00Z",
      "data": {
        "description": "Working on feature X",
        "project_id": "prj_01HN...",
        "started_at": "2025-01-02T22:00:00Z",
        "ended_at": "2025-01-02T23:00:00Z"
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

#### Security: Delegate to Existing Business Logic

The sync engine is a transport layer, not an authorization layer.

Authorization, validation, and business rules already exist in your service layer. The sync engine delegates to these existing services rather than reimplementing them.

```
Don't do this: Sync engine with parallel auth system
┌─────────────────────────────────────────────────────┐
│ sync_push()                                         │
│   └── process_sync_operation()                      │
│         └── can_modify_entity()  ← duplicate auth!  │
│               └── entity.save()  ← bypasses logic!  │
└─────────────────────────────────────────────────────┘

Do this: Sync engine delegates to existing services
┌─────────────────────────────────────────────────────┐
│ sync_push()                                         │
│   └── process_sync_operation()                      │
│         └── ContactService.update()  ← existing!    │
│               ├── authorization     (already there) │
│               ├── validation        (already there) │
│               ├── business rules    (already there) │
│               └── audit logging     (already there) │
└─────────────────────────────────────────────────────┘
```

Sync engine responsibilities:
- Idempotency (don't process same operation twice)
- Batching (handle multiple operations efficiently)
- Conflict resolution (LWW, field merge)
- Cursor management (track sync progress)
- Error aggregation (collect results for batch response)

Delegated to existing services:
- Authorization (who can do what)
- Validation (is the data valid)
- Business rules (domain logic)
- Side effects (notifications, webhooks)
- Audit logging

### Pull Endpoint (Server → Client)

**Endpoint**: `GET /api/v1/sync/pull`

**Query parameters**:
| Param | Default | Description |
|-------|---------|-------------|
| `since` | null | Opaque cursor from previous pull |
| `entity_types` | all | Comma-separated filter |
| `limit` | 100 | Max changes per response (max 500) |

**Response fields**:
| Field | Description |
|-------|-------------|
| `changes` | Array of entity changes |
| `cursor` | Opaque cursor for next page |
| `has_more` | Whether more pages exist |
| `force_resync` | If true, client should do full resync |

Each change contains:
- `entity_type`, `entity_id` - identifies the entity
- `operation` - `upsert` or `delete`
- `data` - entity data (null for deletes)
- `version` - sync version for ordering

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
      "entity_id": "te_01HN8J9K2M3N4P5Q6R8DELETED",
      "operation": "delete",
      "updated_at": "2025-01-02T23:10:00Z"
    }
  ],
  "cursor": "MjAyNS0wMS0wMlQyMzoxMDowMFpfdGVfMDFIOEo5SzJNM040UDVRNlI4REVMRVRFRA==",  // base64({timestamp}_{last_entity_id})
  "has_more": false
}
```

### Operation Intents

| Intent | Meaning |
|--------|---------|
| `create` | New entity |
| `update` | Modify existing (partial data allowed) |
| `delete` | Mark as deleted (tombstone) |

### Cursor Design

The cursor is an opaque base64-encoded token. Internally it encodes:

```
base64({timestamp}_{entity_id})
```

**Why timestamp + ID?**
- Timestamp alone is ambiguous (multiple changes per millisecond)
- Combined value ensures stable ordering

**Why base64?**
- Truly opaque to client—discourages parsing or constructing cursors
- Can change internal format without breaking clients
- URL-safe when using base64url variant

**Monotonicity Guarantees:**

> [!IMPORTANT]
> The cursor must be monotonic from the database, not client clocks. Use `server_timestamp` (assigned on write) as the primary cursor component.

---

## Conflict Resolution Strategies

> **Implementation**: See [`apply_field_level_lww`](../../backend/apps/sync/services.py)

### Conflict Resolution Flow

```
                    ┌─────────────────┐
                    │ Incoming Update │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │    Has FieldLevelLWWMixin?  │
              └──────────────┬──────────────┘
                    ┌────────┴────────┐
                    │                 │
                   Yes                No
                    │                 │
         ┌──────────┴─────┐   ┌───────┴───────┐
         │ For each field:│   │ Compare       │
         │ client_ts >    │   │ entity        │
         │ server_ts?     │   │ updated_at    │
         └───────┬────────┘   └───────┬───────┘
                 │                    │
         ┌───────┴───────┐    ┌───────┴───────┐
         │ Yes: Apply    │    │ Newer wins    │
         │ No: Reject    │    │               │
         │ (log to       │    │               │
         │ conflict_fields)   │               │
         └───────────────┘    └───────────────┘
```

### Strategy Matrix by Use Case

| Use Case | Entity | Strategy | Rationale |
|----------|--------|----------|-----------|
| Field CRM | Contact | LWW by field | Simple, contacts rarely edited concurrently |
| Field CRM | Meeting Note | Append-only + merge | Notes can be appended from multiple sessions |
| Toggl-like | Time Entry | LWW with validation | Atomic updates, server validates no overlaps |
| Toggl-like | Project/Tag | LWW by field | Metadata rarely conflicts |
| Generic B2B | Configurable | Per-entity policy | Let app developers choose |

### Last-Write-Wins (Entity-Level)

Default for simple entities. Compares `client_timestamp` against `entity.updated_at`. Newer wins entirely.

### Last-Write-Wins (Field-Level)

For entities with independent fields (contacts, profiles). Each field is compared separately:
- Client wins if server has no timestamp for the field
- Client wins if `client_timestamp > server_field_timestamp`
- Otherwise server wins, rejected field logged for observability

### Optimistic Concurrency (Optional)

Pass `base_version` in the operation. Server rejects if `entity.sync_version != base_version`. Client must fetch latest state and retry.

### CRDT for Rich Text (Future Enhancement)

For collaborative notes, consider [Yjs](https://yjs.dev/) on the client with server-side merge:

```python
# Simplified CRDT storage for notes
class NoteContent(models.Model):
    note = models.OneToOneField('Note', on_delete=models.CASCADE)

    # Store Yjs document state as binary
    yjs_state = models.BinaryField()
    yjs_state_vector = models.BinaryField()  # For delta sync

    def merge_update(self, client_update: bytes) -> bytes:
        """Apply client Yjs update and return merged state."""
        # Use y-py (Python Yjs bindings) for server-side merge
        import y_py as Y
        doc = Y.YDoc()
        Y.apply_update(doc, self.yjs_state)
        Y.apply_update(doc, client_update)
        self.yjs_state = Y.encode_state_as_update(doc)
        self.save()
        return self.yjs_state
```

### Tombstone Lifecycle

1. Client sends `delete` intent
2. Server sets `deleted_at` (soft delete)
3. Deleted entities included in `pull` responses with `operation: "delete"`
4. Client removes from local DB
5. Server hard-deletes after 90 days (cleanup job)

---

## Client-Side Architecture

> **Platform-specific implementation guides:**
> - [iOS (Swift)](./sync-client-ios.md) - SwiftUI, SwiftData, Swift Concurrency

### Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                    UI Layer                      │
├─────────────────────────────────────────────────┤
│               State Management                   │
├─────────────────────────────────────────────────┤
│                 Sync Engine                      │
│     ┌─────────────┬─────────────┬────────────┐  │
│     │ Operation   │ Sync        │ Conflict   │  │
│     │ Queue       │ Scheduler   │ Resolver   │  │
│     └─────────────┴─────────────┴────────────┘  │
├─────────────────────────────────────────────────┤
│               Local Database                     │
└─────────────────────────────────────────────────┘
```

### Operation Lifecycle

```
    ┌───────────┐     enqueue      ┌─────────┐
    │  Created  │─────────────────►│ Pending │◄─────────┐
    └───────────┘                  └────┬────┘          │
                                        │ sync()       │
                                        ▼              │
                              ┌──────────────────┐     │
                              │     Syncing      │     │
                              └────────┬─────────┘     │
                       ┌───────────────┼───────────────┤
                       ▼               ▼               │
                  ┌─────────┐    ┌──────────┐    ┌─────┴────┐
                  │ Applied │    │ Retryable│    │  Failed  │
                  │(removed)│    │  Error   │────│(permanent)│
                  └─────────┘    └──────────┘    └──────────┘
                                  (backoff)
```

### Key Requirements

1. **Persistent Operation Queue** - Operations must be persisted locally **before** showing success to the user
2. **Client-Side ID Generation** - Use ULIDs for time-ordered, collision-resistant IDs
3. **Exponential Backoff** - Retry transient failures with jitter (max 10 attempts)
4. **Network Awareness** - Pause sync when offline, trigger on reconnect
5. **Partial Batch Handling** - Handle mixed success/failure independently
6. **Background Sync** - Continue syncing when app is backgrounded

See [iOS Client Implementation](./sync-client-ios.md) for retry delays, reliability guarantees, and full code examples.

---

## Example Use Cases

> These are conceptual examples showing how to apply the sync engine to different domains.

### Field CRM

| Entity | Strategy | Rationale |
|--------|----------|-----------|
| Contact | Field-level LWW | Different salespeople may update different fields |
| Interaction | Append-only | Notes from multiple sessions should merge |
| Tag | Entity-level LWW | Simple metadata, low conflict risk |

**Characteristics**: Low write frequency (5-20/day), offline capture is primary use case.

### Time Tracking (Toggl-like)

| Entity | Strategy | Rationale |
|--------|----------|-----------|
| TimeEntry | LWW + server validation | Validate no overlapping entries |
| Project | Field-level LWW | Metadata rarely conflicts |
| Client | Entity-level LWW | Simple reference data |

**Characteristics**: High write frequency (timer updates), field-level accuracy critical.

### Using the Registry

Register entity types with their conflict strategies at app startup:

```python
SyncRegistry.register('contact', Contact, 'lww_field')
SyncRegistry.register('time_entry', TimeEntry, 'lww')
```

See [`apps/sync/registry.py`](../../backend/apps/sync/registry.py) for the full implementation.

---

## Integration with Existing Infrastructure

### Event Flow

```
Client Push → SyncOperation created → Entity updated → OutboxEvent created
                                                              ↓
                                                    publish_events command
                                                              ↓
                                    ┌─────────────────────────┴────────────────────┐
                                    ↓                                              ↓
                            WebhookDelivery                                  AuditLog
                            (Zapier, etc.)                               (Compliance)
```

### Webhook Events for Sync

```python
# Emit after sync operations
SYNC_EVENTS = [
    'contact.created',
    'contact.updated',
    'contact.deleted',
    'time_entry.created',
    'time_entry.updated',
    'time_entry.deleted',
    # Generic pattern: {entity_type}.{action}
]
```

Zapier integration works automatically via existing webhook system.

### Rate Limiting

```python
# apps/sync/throttling.py

SYNC_RATE_LIMITS = {
    'push': {
        'per_device': '100/minute',
        'per_workspace': '1000/minute',
    },
    'pull': {
        'per_device': '60/minute',
        'per_workspace': '600/minute',
    },
}
```

### Server-Side Mutations and Sync Stream

Any server-side mutation that should propagate to clients **must** update `updated_at` to enter the sync stream.

#### Safe Patterns

- Use `.save()` (auto-updates `updated_at`)
- Use `.update(..., updated_at=timezone.now())` for bulk updates

#### Dangerous Patterns (Will Not Sync)

```python
# These bypass updated_at - clients will never see the change!
Contact.objects.filter(...).update(status='active')  # Missing updated_at
cursor.execute("UPDATE contacts SET ...")             # Raw SQL
```

#### Checklist

| Source | Action Required |
|--------|-----------------|
| Management commands | Use `.save()` or explicit `updated_at` |
| Background tasks | Use `.save()` or explicit `updated_at` |
| Admin panel | Use `.save()` or explicit `updated_at` |
| Database triggers | Include `updated_at = NOW()` |
| Data migrations | Include `updated_at` in UPDATE |

---

## Scalability Considerations

### Current Scale

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

### Database Optimizations

For large deployments, consider partitioning the sync_operations table by month:

```sql
CREATE TABLE sync_operations (
    ...
) PARTITION BY RANGE (server_timestamp);
```

### Rate Limiting

Implement per-organization rate limiting:

```python
# Django middleware or decorator
@rate_limit(key="organization:{organization_id}", limit=100, period=60)
def sync_push(request):
    ...
```

---

## Full Re-Sync Triggers

Sometimes the client needs to throw away its cursor and re-sync from scratch.

### When to Trigger Full Re-Sync

| Trigger | Who Initiates | How |
|---------|---------------|-----|
| App upgrade | Client | Compare local schema version with app's expected version |
| Server says cursor invalid | Server | Return `CURSOR_INVALID` error on pull |
| Periodic safety net | Client | Every 24 hours (configurable) |
| User manually requests | User | "Refresh all data" button in settings |
| Server forces it | Server | Set `force_resync: true` in pull response |
| Corrupt local database | Client | Detect SQLite corruption, wipe and re-sync |

### Server: Force Re-Sync Flag

To force all clients to re-sync (e.g., after a data migration), set `force_resync_before` timestamp for the organization. The pull endpoint checks if the client's cursor is older and returns `force_resync: true`.

See [iOS Client Implementation](./sync-client-ios.md#full-re-sync-handling) for client-side handling.

---

## Error Codes

The sync API returns structured errors. Clients should handle each category differently.

### Error Response Format

```json
{
  "idempotency_key": "op_01HN8J...",
  "status": "rejected",
  "error_code": "VALIDATION_ERROR",
  "error_message": "Phone number format invalid",
  "error_details": {"field": "phone", "value": "not-a-phone"}
}
```

### Error Code Reference

| Code | HTTP Status | Retryable | Client Action |
|------|-------------|-----------|---------------|
| `VALIDATION_ERROR` | 400 | No | Show error to user, let them fix |
| `NOT_FOUND` | 404 | No | Remove from local DB (entity was deleted) |
| `FORBIDDEN` | 403 | No | Show "no permission" error |
| `CONFLICT` | 409 | No | Fetch latest server state, re-resolve |
| `ENTITY_ARCHIVED` | 400 | No | Show "cannot modify archived" error |
| `WORKSPACE_SUSPENDED` | 403 | No | Show "workspace suspended" message |
| `RATE_LIMITED` | 429 | Yes | Back off, retry with delay from `Retry-After` header |
| `SERVER_ERROR` | 500 | Yes | Retry with exponential backoff |
| `CURSOR_INVALID` | 400 | No | Trigger full re-sync |
| `DUPLICATE` | 200 | N/A | Operation already processed, treat as success |

### Rate Limit Response

```json
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{
  "error_code": "RATE_LIMITED",
  "error_message": "Rate limit exceeded",
  "retry_after_seconds": 60
}
```

Client should use `retry_after_seconds` as the minimum delay before retrying.

---

## Schema Changes and Versioning

### Entity Schema Changes

Schema changes (adding/removing fields) happen with app releases. The approach is simple:

1. Bump `SCHEMA_VERSION` in the client app
2. On app launch, client detects version mismatch
3. Client triggers full re-sync
4. Done

This avoids complex migration logic. The trade-off is that users re-download all data on upgrade, which is acceptable for most B2B apps with <100k entities per workspace.

```swift
// In your app's version constants
let syncSchemaVersion = 4  // Bump this when you add/remove/rename fields
```

### API Versioning

The sync API lives at `/api/v1/sync/`. If you need breaking changes:

| Change Type | Approach |
|-------------|----------|
| Add optional field to response | No version bump needed |
| Add required field to request | New version (`/api/v2/sync/`) |
| Remove field from response | Deprecate, then remove in v2 |
| Change field type | New version |
| Change conflict resolution behavior | New version |

Maintain old versions for 6-12 months to allow client upgrades.

---

## Failed Operations Handling

What happens when an operation permanently fails (validation error, permission denied, etc.)?

### Client-Side Dead Letter Queue

Operations that fail with non-retryable errors go to a "dead letter" state:
- `status` = failed
- `nextRetryAt` = nil (no more retries)
- `errorCode` and `lastError` populated for user display

See [iOS Client Implementation](./sync-client-ios.md) for the full Swift implementation.

### User Resolution Options

| Option | When to Use |
|--------|-------------|
| Retry | User fixed the issue (e.g., restored permissions) |
| Discard | User accepts data loss |
| Edit and retry | Validation error - fix and resubmit |

### UI Considerations

- Show a badge/indicator when failed operations exist
- Don't block the user from using the app
- Provide a "Sync Issues" screen listing failed operations
- Auto-clear acknowledged failures after 30 days

---

## Compression and Batching

### Response Compression

Enable gzip for sync responses (5-10x reduction for JSON payloads):

```nginx
# nginx (preferred for production)
location /api/v1/sync/ {
    gzip on;
    gzip_types application/json;
    gzip_min_length 1000;
}
```

### Batch Size Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max operations per push | 100 | Prevents timeout, keeps transactions small |
| Max changes per pull | 500 | Balances latency vs round-trips |
| Max payload size | 1MB | Mobile-friendly, fits in memory |

Clients should split large queues into batches of 100 operations.

---

## Background Notifications

Reduce polling by notifying clients when server has changes. Optional—polling works fine for most cases.

### Options

| Method | Latency | Complexity | Best For |
|--------|---------|------------|----------|
| Polling | 30s-5min | Low | Default, always works |
| Push notification | 1-5s | Medium | Mobile apps |
| WebSocket | <100ms | High | Desktop, real-time features |

### Push Notification Flow

```
Server writes entity → OutboxEvent → EventBridge → Lambda → SNS → Mobile push → Client pulls
```

The push notification is a "nudge"—it tells the client "there's new data, go pull." It doesn't contain the actual data (just `{"type": "sync_nudge"}`).

See [iOS Client Implementation](./sync-client-ios.md#push-notification-nudge-handling) for client-side handling.

---

## Testing Strategy

### Server-Side Tests

| Layer | What to Test | Location |
|-------|--------------|----------|
| Unit | Conflict resolution, cursor parsing, LWW logic | `tests/sync/test_services.py` |
| Integration | Push/pull API cycle, idempotency, soft-delete handling | `tests/sync/test_api.py` |

Key test cases:
- Client wins when timestamp is newer
- Server wins when timestamp is newer
- Duplicate idempotency keys return `duplicate` status
- Soft-deleted entities appear in pull with `operation: delete`
- Cursor pagination works correctly

### Client-Side Tests

| Layer | What to Test |
|-------|--------------|
| Unit | Retry policy, backoff calculation, queue operations |
| Integration | Mock server responses, partial batch failure handling |
| E2E | Real server, multi-client sync scenarios |

Key test cases:
- Operations persist before showing success to user
- Retries on 5xx errors with exponential backoff
- No retry on validation errors (4xx)
- Cursor invalid triggers full resync

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ID format | ULIDs | Time-sortable, collision-free, works offline |
| Cursor format | `{timestamp}_{id}` | Monotonic, resumable, stable ordering |
| Default conflict strategy | LWW (field-level) | Simple, covers 90% of cases |
| CRDT library | Yjs (if needed) | Mature, well-documented, TypeScript-native |
| Sync transport | HTTPS REST | Simple, works everywhere, cacheable |
| Real-time (future) | WebSocket for presence only | Sync still via REST for reliability |

---

## Future Considerations

- **Selective Sync**: Allow clients to sync only specific entity types or date ranges
- **Partial Sync Recovery**: Resume interrupted syncs without re-fetching
- **Conflict UI Components**: Reusable UI for manual conflict resolution
