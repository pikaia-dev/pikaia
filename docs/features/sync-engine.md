# Event-Driven Sync Engine Framework Plan

## Executive Summary

Pikaia already has **strong foundations** for a sync engine:
- ✅ Transactional outbox pattern with `OutboxEvent`
- ✅ Webhook delivery system with retry/circuit breaker
- ✅ Soft-delete pattern across models
- ✅ Device linking infrastructure
- ✅ Multi-tenant isolation

What's needed: **Sync endpoints, operation queue, cursor-based pull, and conflict resolution strategies tailored to each use case**.

---

## 1. Architecture Philosophy

### Local-First, Server-Authoritative Hybrid

Based on research from [Sandro Maglione's sync engine lessons](https://www.sandromaglione.com/newsletter/lessons-from-implementing-a-sync-engine) and [DebugAI's local-first analysis](https://debugg.ai/resources/local-first-apps-2025-crdts-replication-edge-storage-offline-sync):

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

**Key principle**: The local database is the Single Source of Truth for the client. The server is authoritative for conflict resolution and final state.

### Design Principles

#### 1. Stale-Read Tolerant

Clients may operate on stale state. This is fundamental to offline-first design:

- Clients do **not** need to be fully up-to-date before pushing changes
- Updates are applied as **field-level patches** (see PATCH semantics below)
- Server resolves conflicts using configured strategy (LWW, merge, etc.)
- Temporary inconsistency is acceptable; eventual consistency is guaranteed

#### 2. PATCH Semantics for Updates

For `update` operations, `data` is a **partial payload**:

```python
# Client sends only changed fields
{
    "intent": "update",
    "entity_id": "ct_01HN8J...",
    "data": {"phone": "+1-555-1234"}  # Only phone changed
}

# Server behavior:
# ✅ Update phone field
# ✅ Preserve all other fields (name, email, company, etc.)
# ❌ Do NOT null out omitted fields
```

**Server implementation MUST**:
- Only update fields present in `data`
- Preserve existing values for omitted fields
- Track field-level timestamps if using field-level LWW

#### 3. Empty Queue ≠ Up-to-Date

An empty local operation queue only means **"no local changes to push"**.

It does **not** imply:
- Client has received all server changes
- Client state matches server state
- No pull is needed

```typescript
// WRONG assumption
if (operationQueue.isEmpty()) {
  console.log("Client is in sync"); // ❌ False!
}

// CORRECT understanding
if (operationQueue.isEmpty()) {
  console.log("No pending local changes"); // ✅
  // Still need to pull to get server changes
}
```

#### 4. Server-Side Mutations Must Enter Sync Stream

**Any server-side mutation** that should be reflected on clients must update the entity's `updated_at` timestamp:

| Mutation Source | Must Update `updated_at`? | Example |
|-----------------|---------------------------|---------|
| Client push | ✅ Yes (automatic via `save()`) | User edits contact |
| Admin panel | ✅ Yes | Admin fixes data |
| Background job | ✅ Yes | Scheduled cleanup |
| Cron task | ✅ Yes | Nightly recalculation |
| Database trigger | ✅ Yes | Denormalization |
| Webhook handler | ✅ Yes | External integration |

```python
# WRONG: Direct update bypasses updated_at
Contact.objects.filter(id=contact_id).update(status='archived')  # ❌

# CORRECT: Use save() or explicit updated_at
contact = Contact.objects.get(id=contact_id)
contact.status = 'archived'
contact.save()  # ✅ updated_at set automatically

# Or with bulk update:
Contact.objects.filter(id=contact_id).update(
    status='archived',
    updated_at=timezone.now(),  # ✅ Explicit
)
```

#### 5. Trade-off: Patch Updates + Eventual Consistency

With field-level patches and stale-read tolerance:

| Scenario | Behavior | Acceptable? |
|----------|----------|-------------|
| Client A and B both update different fields | Both changes merge | ✅ Yes |
| Client A updates field X, server job updates field X | LWW resolves | ✅ Yes |
| Client pulls, server updates entity, client pushes stale patch | Client's field wins (LWW) | ⚠️ Intentional |

**This is acceptable when**:
- Field-level LWW is the configured strategy
- "Last writer wins" is intentional policy
- Business logic doesn't require strict ordering

**Requires additional business logic for**:
- Inventory counts
- Financial balances
- Any domain with constraints that can be violated by concurrent offline writes

Note: LWW sync **does not lose data** in these cases. All operations are recorded. The question is how to handle constraint violations after sync:

```
Example: Inventory over-commitment

Stock: 5 units
Client A (offline): Sells 3 → records sale of 3
Client B (offline): Sells 4 → records sale of 4
Both sync: 7 units sold from 5 available

Sync engine's job: ✅ Record both sales accurately
Business logic's job: Decide what to do
  → Backorder 2 units
  → Cancel later order + notify customer
  → Allow negative stock (common in B2B)
  → Flag for manual review
```

This is a **policy decision**, not a sync failure. The sync engine reliably captures intent; business rules handle reconciliation.

**Use CRDTs for**:
- Collaborative text editing (character-level convergence)
- Counters that must converge (G-Counter, PN-Counter)
- Sets with add/remove semantics (OR-Set)

---

## 2. Core Data Models

### 2.1 Syncable Entity Base

```python
# apps/sync/models.py

from apps.core.models import (
    SoftDeleteManager,
    SoftDeleteAllManager,
    SoftDeleteMixin,
    TimestampedModel,
)

class SyncableModel(SoftDeleteMixin, TimestampedModel):
    """
    Base for all sync-enabled entities.

    Inherits soft-delete behavior from SoftDeleteMixin.
    IMPORTANT: SoftDeleteMixin MUST come before TimestampedModel in MRO
    so that soft_delete() properly updates updated_at timestamp.

    Manager usage:
    - .objects: Excludes deleted records (for normal app queries)
    - .all_objects: Includes deleted records (REQUIRED for sync pull)
    """

    # Managers - follow existing Pikaia pattern
    objects = SoftDeleteManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        abstract = True
        indexes = [
            # Critical for cursor-based pull queries (includes deleted)
            models.Index(fields=['workspace', 'updated_at', 'id']),
        ]

    # Use ULIDs for time-sortable, collision-free IDs
    id = models.CharField(max_length=32, primary_key=True, editable=False)
    workspace = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)

    # Sync metadata
    sync_version = models.PositiveBigIntegerField(default=0)  # Lamport clock
    last_modified_by = models.ForeignKey('accounts.Member', null=True, on_delete=models.SET_NULL)
    device_id = models.CharField(max_length=64, null=True)  # Origin device

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = self._generate_prefixed_ulid()
        self.sync_version += 1
        super().save(*args, **kwargs)
```

### 2.2 Sync Operation Log (Inbound)

```python
class SyncOperation(models.Model):
    """Append-only log of all sync operations for audit and replay."""

    class Intent(models.TextChoices):
        CREATE = 'create'
        UPDATE = 'update'
        DELETE = 'delete'

    class Status(models.TextChoices):
        APPLIED = 'applied'
        REJECTED = 'rejected'
        CONFLICT = 'conflict'
        DUPLICATE = 'duplicate'

    # Idempotency
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)

    # Context
    workspace = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE)
    actor = models.ForeignKey('accounts.Member', on_delete=models.SET_NULL, null=True)
    device_id = models.CharField(max_length=64)

    # Operation details
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=32)
    intent = models.CharField(max_length=16, choices=Intent.choices)

    # Payload & timestamps
    payload = models.JSONField()
    client_timestamp = models.DateTimeField()
    server_timestamp = models.DateTimeField(auto_now_add=True)

    # Resolution
    status = models.CharField(max_length=16, choices=Status.choices)
    resolution_details = models.JSONField(null=True)  # Conflict info

    # Observability metrics (per-operation, negligible overhead)
    drift_ms = models.IntegerField(null=True, help_text="client_timestamp - server_timestamp in ms")
    conflict_fields = models.JSONField(null=True, help_text="Fields that had conflicts (for field-level LWW)")
    client_retry_count = models.PositiveSmallIntegerField(default=0, help_text="Times client retried this op")

    class Meta:
        indexes = [
            models.Index(fields=['workspace', 'server_timestamp']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]
```

#### Observability: Per-Operation Metrics

Since every push already writes to `SyncOperation`, we get per-operation metrics for free:

| Metric | Field | What it tells you |
|--------|-------|-------------------|
| **Drift** | `drift_ms` | How far off are client clocks? |
| **Conflicts** | `conflict_fields` | Which fields conflict most? |
| **Retries** | `client_retry_count` | Network reliability issues? |

**Setting metrics in the handler:**

```python
def process_sync_operation(...) -> SyncResult:
    # Calculate drift (negative = client ahead, positive = client behind)
    drift_ms = int((timezone.now() - operation.client_timestamp).total_seconds() * 1000)

    # Track conflicts from field-level LWW
    conflict_fields = None
    if using_field_level_lww:
        applied, rejected = apply_field_level_lww(entity, operation.data, operation.client_timestamp)
        if rejected:
            conflict_fields = list(rejected.keys())

    # Create the operation log with metrics
    SyncOperation.objects.create(
        idempotency_key=operation.idempotency_key,
        # ... other fields ...
        drift_ms=drift_ms,
        conflict_fields=conflict_fields,
        client_retry_count=operation.retry_count or 0,
        status='applied' if not rejected else 'conflict',
    )
```

**Dashboard queries:**

```sql
-- Average drift by hour (are clocks drifting?)
SELECT
    DATE_TRUNC('hour', server_timestamp) AS hour,
    AVG(drift_ms) AS avg_drift_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY ABS(drift_ms)) AS p95_drift_ms
FROM sync_operations
WHERE server_timestamp > NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY 1;

-- Conflict rate by entity type (which entities conflict most?)
SELECT
    entity_type,
    COUNT(*) AS total_ops,
    SUM(CASE WHEN conflict_fields IS NOT NULL THEN 1 ELSE 0 END) AS conflicts,
    ROUND(100.0 * SUM(CASE WHEN conflict_fields IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS conflict_pct
FROM sync_operations
WHERE server_timestamp > NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY conflict_pct DESC;

-- Most conflicted fields (where should we improve UX?)
SELECT
    field_name,
    COUNT(*) AS conflict_count
FROM sync_operations,
    LATERAL jsonb_array_elements_text(conflict_fields) AS field_name
WHERE conflict_fields IS NOT NULL
    AND server_timestamp > NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY 2 DESC;

-- Retry patterns (network issues by device/user?)
SELECT
    device_id,
    AVG(client_retry_count) AS avg_retries,
    MAX(client_retry_count) AS max_retries,
    COUNT(*) AS total_ops
FROM sync_operations
WHERE server_timestamp > NOW() - INTERVAL '7 days'
GROUP BY 1
HAVING AVG(client_retry_count) > 1
ORDER BY avg_retries DESC;
```

**What the metrics tell you:**

| Metric | Normal | Warning | Action |
|--------|--------|---------|--------|
| `avg_drift_ms` | < 1000ms | > 5000ms | Client clocks off, warn user |
| `conflict_pct` | < 5% | > 20% | UX issue - users editing same things |
| `avg_retries` | < 0.5 | > 2 | Network issues, check connectivity |

### 2.3 Field-Level Timestamps for LWW

Field-level Last-Write-Wins requires tracking **when each field was last modified**, not just the entity as a whole.

#### Storage Format

```python
# apps/sync/models.py

class FieldLevelLWWMixin(models.Model):
    """
    Mixin for entities using field-level LWW conflict resolution.

    Tracks per-field modification timestamps to enable granular merge.
    """

    class Meta:
        abstract = True

    # JSON object mapping field names to ISO timestamps
    # Example: {"name": "2025-01-23T10:00:00Z", "phone": "2025-01-23T09:30:00Z"}
    field_timestamps = models.JSONField(
        default=dict,
        help_text="Per-field modification timestamps for LWW resolution",
    )

    def update_field_timestamp(self, field: str, timestamp: datetime) -> None:
        """Update the timestamp for a single field."""
        self.field_timestamps[field] = timestamp.isoformat()

    def get_field_timestamp(self, field: str) -> datetime | None:
        """Get the timestamp for a field, or None if never set."""
        ts = self.field_timestamps.get(field)
        if ts:
            return datetime.fromisoformat(ts)
        return None

    def update_fields_with_timestamps(
        self,
        updates: dict,
        timestamp: datetime,
    ) -> None:
        """
        Update multiple fields and their timestamps atomically.
        Call this instead of setting fields directly.
        """
        for field, value in updates.items():
            setattr(self, field, value)
            self.update_field_timestamp(field, timestamp)
```

#### Write Path: Updating Field Timestamps

```python
# apps/sync/services.py

def apply_field_level_lww(
    entity: FieldLevelLWWMixin,
    client_data: dict,
    client_timestamp: datetime,
) -> tuple[dict, dict]:
    """
    Apply field-level LWW merge.

    Returns:
        (applied_fields, rejected_fields)
        - applied_fields: {field: value} that were applied
        - rejected_fields: {field: {client: v1, server: v2}} that were rejected
    """
    applied = {}
    rejected = {}

    for field, client_value in client_data.items():
        server_value = getattr(entity, field, None)
        server_ts = entity.get_field_timestamp(field)

        # Client wins if:
        # 1. Server has no timestamp for this field (new field or migration)
        # 2. Client timestamp is newer than server timestamp
        if server_ts is None or client_timestamp > server_ts:
            setattr(entity, field, client_value)
            entity.update_field_timestamp(field, client_timestamp)
            applied[field] = client_value
        else:
            # Server wins - field was modified more recently
            if client_value != server_value:
                rejected[field] = {
                    'client_value': client_value,
                    'client_timestamp': client_timestamp.isoformat(),
                    'server_value': server_value,
                    'server_timestamp': server_ts.isoformat(),
                }

    if applied:
        # Also update entity-level updated_at for sync stream
        entity.save()

    return applied, rejected
```

#### Migration Strategy for Existing Data

For entities that exist before field-level LWW is implemented:

```python
# Option 1: Treat missing timestamps as "infinitely old"
# Any incoming update wins. This is the default behavior above (server_ts is None → client wins)

# Option 2: Backfill with entity's updated_at
# apps/sync/management/commands/backfill_field_timestamps.py

class Command(BaseCommand):
    """Backfill field_timestamps for existing entities."""

    help = "Initialize field_timestamps from entity updated_at for existing records"

    def handle(self, *args, **options):
        for model in SyncRegistry.get_lww_models():
            # Get syncable fields (exclude id, timestamps, etc.)
            syncable_fields = model.get_syncable_fields()

            updated = 0
            for entity in model.all_objects.filter(field_timestamps={}):
                # Initialize all fields to entity's updated_at
                entity.field_timestamps = {
                    field: entity.updated_at.isoformat()
                    for field in syncable_fields
                }
                entity.save(update_fields=['field_timestamps'])
                updated += 1

            self.stdout.write(f"{model.__name__}: backfilled {updated} records")
```

#### Defining Syncable Fields

```python
# apps/sync/models.py

class FieldLevelLWWMixin(models.Model):
    # ... existing code ...

    # Fields to exclude from LWW tracking
    LWW_EXCLUDED_FIELDS = {
        'id', 'workspace', 'workspace_id',
        'created_at', 'updated_at', 'deleted_at',
        'sync_version', 'field_timestamps',
        'last_modified_by', 'last_modified_by_id',
        'device_id',
    }

    @classmethod
    def get_syncable_fields(cls) -> list[str]:
        """Return list of fields that participate in field-level LWW."""
        return [
            f.name for f in cls._meta.get_fields()
            if f.concrete
            and not f.primary_key
            and f.name not in cls.LWW_EXCLUDED_FIELDS
        ]
```

#### Client-Side: Sending Field Timestamps

Clients should track when they modified each field locally:

```typescript
// client/models/Contact.ts

interface FieldTimestamps {
  [fieldName: string]: string; // ISO timestamp
}

interface Contact {
  id: string;
  name: string;
  phone: string;
  email: string;
  // ... other fields

  // Track local modification times
  _fieldTimestamps: FieldTimestamps;
}

// When user edits a field
function updateContactField(contact: Contact, field: string, value: any): Contact {
  return {
    ...contact,
    [field]: value,
    _fieldTimestamps: {
      ...contact._fieldTimestamps,
      [field]: new Date().toISOString(),
    },
  };
}

// When creating sync operation, use the field's timestamp
function createSyncOperation(contact: Contact, changedFields: string[]): SyncOperation {
  const data: Record<string, any> = {};
  let latestTimestamp = new Date(0);

  for (const field of changedFields) {
    data[field] = contact[field];
    const fieldTs = new Date(contact._fieldTimestamps[field]);
    if (fieldTs > latestTimestamp) {
      latestTimestamp = fieldTs;
    }
  }

  return {
    idempotencyKey: generateULID(),
    entityType: 'contact',
    entityId: contact.id,
    intent: 'update',
    clientTimestamp: latestTimestamp, // Use latest field timestamp
    data,
  };
}
```

#### When to Use Field-Level vs Entity-Level LWW

| Scenario | Recommendation |
|----------|----------------|
| Simple entities (tags, labels) | Entity-level LWW (simpler) |
| Entities with independent fields (contacts) | Field-level LWW |
| Entities where fields are related (address fields) | Entity-level or grouped field LWW |
| High-conflict entities | Consider CRDT or manual resolution |

---

## 3. Sync Protocol

### 3.0 Soft-Delete Semantics in Sync

**Critical**: The existing `SoftDeleteMixin` pattern requires careful handling in sync operations.

#### The Problem

```python
# Default manager excludes deleted records
Contact.objects.filter(updated_at__gt=cursor)  # ❌ Misses deletions!

# all_objects includes everything
Contact.all_objects.filter(updated_at__gt=cursor)  # ✅ Includes deletions
```

#### The Solution

1. **Pull queries MUST use `.all_objects`** to include soft-deleted records
2. **Existing `soft_delete()` already updates `updated_at`** (see `core/models.py:158`), so deletions appear in cursor-based queries
3. **Return `operation: 'delete'`** for records where `deleted_at IS NOT NULL`
4. **Tombstone retention**: Keep deleted records for 90 days before hard-delete (allows late-syncing clients to receive deletions)

#### Implementation

```python
# apps/sync/services.py

def fetch_changes_for_pull(
    workspace: Organization,
    entity_type: str,
    since_timestamp: datetime | None,
    since_id: str | None,
    limit: int,
) -> list[ChangeOut]:
    """
    Fetch changes including soft-deleted records.

    IMPORTANT: Uses all_objects to include deletions.
    """
    model = SyncRegistry.get_model(entity_type)

    # MUST use all_objects to include soft-deleted records
    qs = model.all_objects.filter(workspace=workspace)

    if since_timestamp:
        # Cursor-based pagination: records updated after cursor
        qs = qs.filter(
            models.Q(updated_at__gt=since_timestamp) |
            models.Q(updated_at=since_timestamp, id__gt=since_id)
        )

    qs = qs.order_by('updated_at', 'id')[:limit]

    changes = []
    for entity in qs:
        changes.append(ChangeOut(
            entity_type=entity_type,
            entity_id=entity.id,
            # Key: deleted records get operation='delete'
            operation='delete' if entity.deleted_at else 'upsert',
            # Deleted records: only send id, no data payload
            data=serialize_entity(entity) if not entity.deleted_at else None,
            version=entity.sync_version,
            updated_at=entity.updated_at,
        ))

    return changes
```

#### Tombstone Cleanup

```python
# apps/sync/management/commands/cleanup_tombstones.py

class Command(BaseCommand):
    """Hard-delete tombstones older than retention period."""

    help = "Remove soft-deleted sync entities past retention period"

    def add_arguments(self, parser):
        parser.add_argument(
            '--retention-days',
            type=int,
            default=90,
            help='Days to retain tombstones (default: 90)',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options['retention_days'])

        for model in SyncRegistry.get_all_models():
            tombstones = model.all_objects.filter(
                deleted_at__isnull=False,
                deleted_at__lt=cutoff,
            )
            count = tombstones.count()

            if not options['dry_run']:
                tombstones.hard_delete()

            self.stdout.write(f"{model.__name__}: {count} tombstones {'would be' if options['dry_run'] else ''} removed")
```

#### Client Handling of Deletions

```typescript
// client/sync/SyncEngine.ts

async processPullResponse(response: SyncPullResponse): Promise<void> {
  for (const change of response.changes) {
    if (change.operation === 'delete') {
      // Remove from local database
      await this.db.delete(change.entityType, change.entityId);
      // Also remove any pending operations for this entity
      await this.operationQueue.removeForEntity(change.entityType, change.entityId);
    } else {
      // Upsert: insert or update
      await this.db.upsert(change.entityType, change.entityId, change.data);
    }
  }

  // Persist new cursor
  await this.db.setCursor(response.cursor);
}
```

#### Index Optimization

```sql
-- Updated index: include deleted_at for efficient tombstone queries
-- Note: NO partial index (WHERE deleted_at IS NULL) - we need ALL records
CREATE INDEX idx_syncable_pull ON {entity_table}
    (workspace_id, updated_at, id);

-- Separate index for tombstone cleanup
CREATE INDEX idx_syncable_tombstones ON {entity_table}
    (deleted_at)
    WHERE deleted_at IS NOT NULL;
```

### 3.0.1 Cursor Ordering and Clock Skew

**Problem**: With multiple Django instances (ECS tasks), clock skew can cause missed records.

```
Timeline (wall clock):  ─────────────────────────────────────────►

Server A (clock +50ms fast):  Saves entity X at "10:00:00.150"
Server B (clock -50ms slow):            Saves entity Y at "10:00:00.050"
                                        (actually happened AFTER X)

Client pulls with cursor "10:00:00.150"
→ Entity Y (timestamp "10:00:00.050") is NEVER returned
→ Client permanently misses entity Y
```

#### Critical: Server Timestamps vs Client Timestamps

The cursor **MUST** use server-controlled values, never client-supplied timestamps:

| Field | Source | Used For |
|-------|--------|----------|
| `updated_at` | Server (`auto_now=True`) | **Cursor** - ordering pull results |
| `sync_version` | Server (incremented on save) | **Cursor** (alternative) - guaranteed ordering |
| `client_timestamp` | Client | **Conflict resolution only** - LWW comparison |

```python
# In push handler:
operation.client_timestamp  # ← Used for LWW conflict resolution
entity.updated_at           # ← Set by server, used for cursor/pull ordering

# These are DIFFERENT timestamps with DIFFERENT purposes:
# - client_timestamp: "when did the user make this change?" (for LWW)
# - updated_at: "when did the server persist this?" (for cursor)
```

**Why this matters**: If the cursor used `client_timestamp`:
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
| **NOT used for cursor** | `client_timestamp` | Only for LWW conflict resolution |

#### Solution: Overlap Window

Pull queries go back slightly from the cursor to catch clock-skewed records. Client idempotency handles duplicates.

```python
# apps/sync/services.py

# Clock skew tolerance: 100ms covers typical NTP drift
CLOCK_SKEW_TOLERANCE = timedelta(milliseconds=100)

def fetch_changes_for_pull(
    workspace: Organization,
    entity_type: str,
    since_timestamp: datetime | None,
    since_id: str | None,
    limit: int,
) -> list[ChangeOut]:
    """
    Fetch changes with overlap window for clock skew tolerance.
    """
    model = SyncRegistry.get_model(entity_type)
    qs = model.all_objects.filter(workspace=workspace)

    if since_timestamp:
        # Apply overlap window to catch clock-skewed records
        # Client must handle duplicates idempotently
        safe_since = since_timestamp - CLOCK_SKEW_TOLERANCE

        qs = qs.filter(
            models.Q(updated_at__gt=safe_since) |
            models.Q(updated_at=safe_since, id__gt=since_id)
        )

    qs = qs.order_by('updated_at', 'id')[:limit]
    return [serialize_change(entity) for entity in qs]
```

#### Client Idempotency for Overlap

```typescript
// client/sync/SyncEngine.ts

async processPullResponse(response: SyncPullResponse): Promise<void> {
  for (const change of response.changes) {
    // Idempotent upsert - handles duplicates from overlap window
    const existing = await this.db.get(change.entityType, change.entityId);

    if (change.operation === 'delete') {
      await this.db.delete(change.entityType, change.entityId);
    } else if (!existing || existing.version < change.version) {
      // Only apply if newer than local version
      await this.db.upsert(change.entityType, change.entityId, change.data);
    }
    // else: duplicate from overlap window, skip
  }

  await this.db.setCursor(response.cursor);
}
```

#### Optional: Monotonic Sequence for High-Consistency

For use cases requiring **guaranteed global ordering** (e.g., financial transactions), add a database sequence:

```python
# apps/sync/models.py

class SyncableModel(SoftDeleteMixin, TimestampedModel):
    # ... existing fields ...

    # Optional: monotonic sequence for guaranteed ordering
    # Use this as cursor instead of updated_at for high-consistency needs
    sync_sequence_id = models.BigIntegerField(
        null=True,
        db_index=True,
        help_text="Monotonic sequence ID from database, guarantees global ordering",
    )

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = self._generate_prefixed_ulid()
        self.sync_version += 1
        super().save(*args, **kwargs)

        # Assign sequence ID after save (requires raw SQL or trigger)
        # This ensures ordering matches commit order, not save() call order
```

```sql
-- Database sequence for guaranteed ordering
CREATE SEQUENCE sync_global_seq;

-- Trigger to assign on insert/update (PostgreSQL)
CREATE OR REPLACE FUNCTION assign_sync_sequence()
RETURNS TRIGGER AS $$
BEGIN
    NEW.sync_sequence_id := nextval('sync_global_seq');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_sequence
    BEFORE INSERT OR UPDATE ON {entity_table}
    FOR EACH ROW
    EXECUTE FUNCTION assign_sync_sequence();
```

#### Periodic Full Sync Recommendation

Even with overlap windows, recommend periodic full syncs to catch edge cases:

```typescript
// client/sync/SyncEngine.ts

class SyncEngine {
  private lastFullSync: Date | null = null;
  private FULL_SYNC_INTERVAL = 24 * 60 * 60 * 1000; // 24 hours

  async triggerSync(): Promise<void> {
    const needsFullSync = !this.lastFullSync ||
      Date.now() - this.lastFullSync.getTime() > this.FULL_SYNC_INTERVAL;

    if (needsFullSync) {
      // Full sync: pull from beginning
      await this.pullChanges(null); // since=null
      this.lastFullSync = new Date();
    } else {
      // Incremental sync
      await this.pullChanges(this.lastCursor);
    }
  }
}
```

#### Summary: When to Use Which Approach

| Scenario | Recommended Cursor | Notes |
|----------|-------------------|-------|
| **Most B2B apps** | `updated_at` + overlap | Simple, handles 99.9% of cases |
| **High-write frequency** | `updated_at` + overlap + periodic full sync | Safety net for edge cases |
| **Financial/audit-critical** | `sync_sequence_id` | Guaranteed ordering, slight perf cost |
| **Collaborative editing** | CRDT (no cursor needed) | Convergence is automatic |

### 3.1 Push Endpoint (Client → Server)

```python
# apps/sync/api.py

class SyncOperationIn(Schema):
    idempotency_key: str  # Client-generated, survives retries
    entity_type: str
    entity_id: str
    intent: Literal['create', 'update', 'delete']
    client_timestamp: datetime
    base_version: int | None = None  # For optimistic concurrency

    # PATCH semantics for 'update' intent:
    # - data contains ONLY changed fields
    # - Omitted fields are NOT overwritten on server
    # - For 'create': data is complete entity
    # - For 'delete': data is ignored (can be empty {})
    data: dict

class SyncPushRequest(Schema):
    operations: list[SyncOperationIn]  # Max 100 per batch

class SyncResultOut(Schema):
    idempotency_key: str
    status: Literal['applied', 'rejected', 'conflict', 'duplicate']
    server_timestamp: datetime
    server_version: int | None = None
    error_code: str | None = None
    conflict_data: dict | None = None  # Server state if conflict

@router.post("/push", response=list[SyncResultOut])
def sync_push(request: AuthenticatedHttpRequest, payload: SyncPushRequest):
    results = []

    for op in payload.operations:
        result = process_sync_operation(
            workspace=request.organization,
            actor=request.member,
            operation=op,
        )
        results.append(result)

        # Emit event for webhooks/integrations
        if result.status == 'applied':
            publish_event(
                event_type=f"{op.entity_type}.synced",
                aggregate=result.entity,
                data=op.data,
                actor=request.user,
                organization_id=request.organization.id,
            )

    return results
```

#### Security: Delegate to Existing Business Logic

**The sync engine is a transport layer, not an authorization layer.**

Authorization, validation, and business rules already exist in your service layer. The sync engine should delegate to these existing services rather than reimplementing them.

```
WRONG: Sync engine with parallel auth system
┌─────────────────────────────────────────────────────┐
│ sync_push()                                         │
│   └── process_sync_operation()                      │
│         └── can_modify_entity()  ← DUPLICATE AUTH!  │
│               └── entity.save()  ← BYPASSES LOGIC!  │
└─────────────────────────────────────────────────────┘

RIGHT: Sync engine delegates to existing services
┌─────────────────────────────────────────────────────┐
│ sync_push()                                         │
│   └── process_sync_operation()                      │
│         └── ContactService.update()  ← EXISTING!    │
│               ├── authorization     (already there) │
│               ├── validation        (already there) │
│               ├── business rules    (already there) │
│               └── audit logging     (already there) │
└─────────────────────────────────────────────────────┘
```

**Sync engine responsibilities:**
- Idempotency (don't process same operation twice)
- Batching (handle multiple operations efficiently)
- Conflict resolution (LWW, field merge)
- Cursor management (track sync progress)
- Error aggregation (collect results for batch response)

**Delegated to existing services:**
- Authorization (who can do what)
- Validation (is the data valid)
- Business rules (domain logic)
- Side effects (notifications, webhooks)
- Audit logging

```python
# apps/sync/services.py

from apps.contacts.services import ContactService
from apps.timetracker.services import TimeEntryService

# Registry maps entity types to their service classes
SERVICE_REGISTRY = {
    'contact': ContactService,
    'time_entry': TimeEntryService,
    # ... other entity types
}

def process_sync_operation(
    workspace: Organization,
    actor: Member,
    operation: SyncOperationIn,
) -> SyncResult:
    """
    Process sync operation by delegating to existing service layer.

    The service layer handles auth, validation, and business logic.
    We handle idempotency and conflict resolution.
    """
    # 1. Idempotency check
    if SyncOperation.objects.filter(idempotency_key=operation.idempotency_key).exists():
        return SyncResult(status='duplicate')

    # 2. Get the appropriate service
    service_class = SERVICE_REGISTRY.get(operation.entity_type)
    if not service_class:
        return SyncResult(status='rejected', error_code='UNKNOWN_ENTITY_TYPE')

    service = service_class(workspace=workspace, actor=actor)

    # 3. Delegate to service (which has all the business logic)
    try:
        if operation.intent == 'create':
            entity = service.create(**operation.data)

        elif operation.intent == 'update':
            # Apply conflict resolution first if needed
            resolved_data = resolve_conflicts(
                workspace, operation.entity_type, operation.entity_id,
                operation.data, operation.client_timestamp
            )
            entity = service.update(operation.entity_id, **resolved_data)

        elif operation.intent == 'delete':
            service.delete(operation.entity_id)
            entity = None

        # 4. Log the operation
        SyncOperation.objects.create(
            idempotency_key=operation.idempotency_key,
            workspace=workspace,
            actor=actor,
            entity_type=operation.entity_type,
            entity_id=operation.entity_id,
            intent=operation.intent,
            payload=operation.data,
            client_timestamp=operation.client_timestamp,
            status='applied',
        )

        return SyncResult(
            status='applied',
            server_timestamp=entity.updated_at if entity else timezone.now(),
            server_version=entity.sync_version if entity else None,
        )

    except PermissionDenied:
        return SyncResult(status='rejected', error_code='FORBIDDEN')
    except ValidationError as e:
        return SyncResult(status='rejected', error_code='VALIDATION_ERROR', details=e.messages)
    except ObjectDoesNotExist:
        return SyncResult(status='rejected', error_code='NOT_FOUND')
```

**Service layer example (already exists in your app):**

```python
# apps/contacts/services.py

class ContactService:
    def __init__(self, workspace: Organization, actor: Member):
        self.workspace = workspace
        self.actor = actor

    def update(self, contact_id: str, **data) -> Contact:
        contact = Contact.objects.get(id=contact_id, workspace=self.workspace)

        # Authorization (already implemented)
        if not self._can_edit(contact):
            raise PermissionDenied("Cannot edit this contact")

        # Validation (already implemented)
        self._validate_update(contact, data)

        # Business logic (already implemented)
        for field, value in data.items():
            setattr(contact, field, value)
        contact.save()

        # Side effects (already implemented)
        self._notify_if_needed(contact)

        return contact

    def _can_edit(self, contact: Contact) -> bool:
        # Your existing authorization logic
        ...
```

**Key insight**: The sync engine adds offline/batching capabilities to your existing API. It doesn't replace your business logic—it routes through it.

### 3.2 Pull Endpoint (Server → Client)

```python
class SyncPullRequest(Schema):
    since: str | None = None  # Opaque cursor
    entity_types: list[str] | None = None  # Filter
    limit: int = Field(default=100, le=500)

class ChangeOut(Schema):
    entity_type: str
    entity_id: str
    operation: Literal['upsert', 'delete']
    data: dict | None
    version: int
    updated_at: datetime

class SyncPullResponse(Schema):
    changes: list[ChangeOut]
    cursor: str  # Opaque, encodes timestamp + id
    has_more: bool

@router.get("/pull", response=SyncPullResponse)
def sync_pull(request: AuthenticatedHttpRequest, params: Query[SyncPullRequest]):
    cursor = parse_cursor(params.since)  # {timestamp, last_id}

    # Query all syncable entities changed since cursor
    changes = fetch_changes(
        workspace=request.organization,
        since_timestamp=cursor.timestamp,
        since_id=cursor.last_id,
        entity_types=params.entity_types,
        limit=params.limit + 1,  # +1 to detect has_more
    )

    has_more = len(changes) > params.limit
    changes = changes[:params.limit]

    next_cursor = encode_cursor(changes[-1]) if changes else params.since

    return SyncPullResponse(
        changes=changes,
        cursor=next_cursor,
        has_more=has_more,
    )
```

---

## 4. Conflict Resolution Strategies

Based on [offline-first best practices](https://medium.com/@jusuftopic/offline-first-architecture-designing-for-reality-not-just-the-cloud-e5fd18e50a59) and [OT vs CRDT analysis](https://dev.to/puritanic/building-collaborative-interfaces-operational-transforms-vs-crdts-2obo):

### Strategy Matrix by Use Case

| Use Case | Entity | Strategy | Rationale |
|----------|--------|----------|-----------|
| **Snowball CRM** | Contact | LWW by field | Simple, contacts rarely edited concurrently |
| **Snowball CRM** | Meeting Note | Append-only + merge | Notes can be appended from multiple sessions |
| **Toggl-like** | Time Entry | LWW with validation | Atomic updates, server validates no overlaps |
| **Toggl-like** | Project/Tag | LWW by field | Metadata rarely conflicts |
| **Generic B2B** | Configurable | Per-entity policy | Let app developers choose |

### 4.1 Last-Write-Wins (Field-Level)

```python
def resolve_lww_field_level(
    server_entity: SyncableModel,
    client_data: dict,
    client_timestamp: datetime,
) -> tuple[dict, dict]:
    """
    Merge client changes with server state at field level.
    Returns (merged_data, conflict_fields).
    """
    merged = {}
    conflicts = {}

    for field, client_value in client_data.items():
        server_value = getattr(server_entity, field, None)
        server_field_ts = server_entity.field_timestamps.get(field)

        if server_field_ts is None or client_timestamp > server_field_ts:
            merged[field] = client_value
        else:
            merged[field] = server_value
            if client_value != server_value:
                conflicts[field] = {
                    'client': client_value,
                    'server': server_value,
                }

    return merged, conflicts
```

### 4.2 Optimistic Concurrency with Version

```python
def resolve_with_version_check(
    server_entity: SyncableModel,
    client_data: dict,
    base_version: int,
) -> SyncResult:
    """
    Reject if server has advanced beyond client's base version.
    """
    if server_entity.sync_version != base_version:
        return SyncResult(
            status='conflict',
            error_code='VERSION_MISMATCH',
            conflict_data={
                'server_version': server_entity.sync_version,
                'server_state': serialize(server_entity),
            },
        )

    # Apply update
    for field, value in client_data.items():
        setattr(server_entity, field, value)
    server_entity.save()

    return SyncResult(status='applied', server_version=server_entity.sync_version)
```

### 4.3 CRDT for Rich Text (Future Enhancement)

For collaborative notes in Snowball, consider [Yjs](https://yjs.dev/) on the client with server-side merge:

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

---

## 5. Client-Side Architecture

### 5.1 Persistent Operation Queue

Based on [Android offline-first architecture](https://developer.android.com/topic/architecture/data-layer/offline-first):

```typescript
// client/sync/OperationQueue.ts

interface PendingOperation {
  idempotencyKey: string;
  entityType: string;
  entityId: string;
  intent: 'create' | 'update' | 'delete';
  data: object;
  clientTimestamp: Date;
  baseVersion?: number;
  status: 'pending' | 'syncing' | 'failed';
  attempts: number;
  lastError?: string;
  createdAt: Date;
}

class OperationQueue {
  private db: SQLiteDatabase;

  async enqueue(op: Omit<PendingOperation, 'status' | 'attempts' | 'createdAt'>): Promise<void> {
    // MUST persist before returning to caller
    await this.db.insert('pending_operations', {
      ...op,
      status: 'pending',
      attempts: 0,
      createdAt: new Date(),
    });
  }

  async processQueue(): Promise<void> {
    const pending = await this.db.query(
      'SELECT * FROM pending_operations WHERE status != "syncing" ORDER BY createdAt'
    );

    const batch = pending.slice(0, 100);
    await this.markSyncing(batch);

    try {
      const results = await this.syncClient.push(batch);
      await this.processResults(results);
    } catch (error) {
      await this.handleBatchError(batch, error);
    }
  }
}
```

#### Exponential Backoff with Jitter

**Problem**: When the server goes down, all clients retry at the same time (thundering herd).

```
Without backoff:                    With backoff + jitter:
┌────────────────────────────┐     ┌────────────────────────────┐
│ 10:00:01 - 1000 retry      │     │ 10:00:01 - 50 retry        │
│ 10:00:02 - 1000 retry      │     │ 10:00:02 - 80 retry        │
│ 10:00:03 - 1000 retry      │     │ 10:00:03 - 120 retry       │
│ Server crushed repeatedly  │     │ Load spread over time ✅   │
└────────────────────────────┘     └────────────────────────────┘
```

**Solution**: Wait longer after each failure, with random variation.

```typescript
// client/sync/RetryStrategy.ts

interface RetryConfig {
  baseDelayMs: number;      // Starting delay (e.g., 1000ms)
  maxDelayMs: number;       // Cap the delay (e.g., 5 minutes)
  maxAttempts: number;      // Give up after N attempts
  jitterFactor: number;     // 0.5 = ±50% randomness
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  baseDelayMs: 1000,        // Start with 1 second
  maxDelayMs: 5 * 60 * 1000, // Max 5 minutes
  maxAttempts: 10,
  jitterFactor: 0.5,        // ±50% jitter
};

/**
 * Calculate delay for retry attempt with exponential backoff + jitter.
 *
 * Exponential: delay doubles each attempt (1s, 2s, 4s, 8s, 16s...)
 * Jitter: add randomness so clients don't retry in sync
 *
 * Example with jitterFactor=0.5:
 *   Base delay: 4000ms
 *   Jitter range: 2000ms to 6000ms (±50%)
 *   Actual delay: random value in that range
 */
function calculateRetryDelay(attempt: number, config: RetryConfig = DEFAULT_RETRY_CONFIG): number {
  // Exponential: 2^attempt * baseDelay
  const exponentialDelay = Math.min(
    config.baseDelayMs * Math.pow(2, attempt),
    config.maxDelayMs
  );

  // Jitter: multiply by random factor between (1-jitter) and (1+jitter)
  const jitterMin = 1 - config.jitterFactor;
  const jitterMax = 1 + config.jitterFactor;
  const jitterMultiplier = jitterMin + Math.random() * (jitterMax - jitterMin);

  return Math.floor(exponentialDelay * jitterMultiplier);
}

// Example outputs for attempt 3 (base delay 1000ms):
// Without jitter: always 8000ms
// With jitter (±50%): random between 4000ms and 12000ms
```

**Retry logic in OperationQueue:**

```typescript
// client/sync/OperationQueue.ts

class OperationQueue {
  private retryConfig = DEFAULT_RETRY_CONFIG;

  async handleBatchError(batch: PendingOperation[], error: Error): Promise<void> {
    const isRetryable = this.isRetryableError(error);

    for (const op of batch) {
      op.attempts += 1;

      if (!isRetryable || op.attempts >= this.retryConfig.maxAttempts) {
        // Permanent failure - move to dead letter queue or notify user
        op.status = 'failed';
        op.lastError = error.message;
      } else {
        // Schedule retry with exponential backoff + jitter
        const delayMs = calculateRetryDelay(op.attempts, this.retryConfig);
        op.status = 'pending';
        op.retryAfter = new Date(Date.now() + delayMs);
      }

      await this.db.update('pending_operations', op.idempotencyKey, op);
    }
  }

  /**
   * Determine if error is retryable.
   *
   * Retryable: network issues, 5xx, 429 (rate limit)
   * Not retryable: 4xx (validation, auth, not found)
   */
  isRetryableError(error: Error): boolean {
    if (error instanceof NetworkError) return true;
    if (error instanceof HttpError) {
      const status = error.status;
      // 5xx = server error, retry
      if (status >= 500) return true;
      // 429 = rate limited, retry after backoff
      if (status === 429) return true;
      // 4xx = client error, don't retry (won't help)
      return false;
    }
    // Unknown error, assume retryable
    return true;
  }

  /**
   * Get operations ready to process (pending + past retry time).
   */
  async getReadyOperations(): Promise<PendingOperation[]> {
    const now = new Date();
    return this.db.query(
      `SELECT * FROM pending_operations
       WHERE status = 'pending'
       AND (retry_after IS NULL OR retry_after <= ?)
       ORDER BY created_at`,
      [now.toISOString()]
    );
  }
}
```

**Retry delays example:**

| Attempt | Base Delay | With Jitter (±50%) |
|---------|------------|-------------------|
| 1 | 1s | 0.5s - 1.5s |
| 2 | 2s | 1s - 3s |
| 3 | 4s | 2s - 6s |
| 4 | 8s | 4s - 12s |
| 5 | 16s | 8s - 24s |
| 6 | 32s | 16s - 48s |
| 7 | 64s | 32s - 96s |
| 8 | 128s | 64s - 192s |
| 9 | 256s | 128s - 384s |
| 10 | 300s (capped) | 150s - 450s |

### 5.2 Sync State Machine

```typescript
// client/sync/SyncEngine.ts

type SyncState =
  | { status: 'idle' }
  | { status: 'pushing', batchSize: number }
  | { status: 'pulling', cursor: string | null }
  | { status: 'error', error: Error, retryAt: Date };

class SyncEngine {
  private state: SyncState = { status: 'idle' };
  private pullInterval = 30_000; // 30 seconds

  async start(): Promise<void> {
    // Listen for network changes
    NetInfo.addEventListener(state => {
      if (state.isConnected) {
        this.triggerSync();
      }
    });

    // Periodic sync - IMPORTANT: Always pull even if queue is empty
    // Empty queue only means "no local changes", NOT "up-to-date with server"
    setInterval(() => this.triggerSync(), this.pullInterval);
  }

  async triggerSync(): Promise<void> {
    if (this.state.status !== 'idle') return;

    // Push first (client changes take priority)
    await this.pushPendingOperations();

    // ALWAYS pull after push, regardless of queue state
    // Server may have changes from other clients, admin, background jobs, etc.
    await this.pullChanges();
  }

  /**
   * Check if client has pending local changes.
   * WARNING: This does NOT indicate sync status with server.
   */
  hasPendingChanges(): boolean {
    return !this.operationQueue.isEmpty();
  }

  /**
   * Check if client is likely in sync with server.
   * Note: This is a heuristic, not a guarantee.
   */
  isLikelySynced(): boolean {
    return (
      this.operationQueue.isEmpty() &&           // No pending local changes
      this.state.status === 'idle' &&            // Not currently syncing
      this.lastPullAt !== null &&                // Has pulled at least once
      Date.now() - this.lastPullAt < 60_000      // Pulled within last minute
    );
  }
}
```

---

## 6. Use Case Implementations

### 6.1 Snowball (Field CRM)

**Entities to sync:**
- `Contact` - name, company, email, phone, notes, tags
- `Interaction` - contact_id, type, content, occurred_at, location
- `Tag` - name, color

**Sync characteristics:**
- Low write frequency (5-20 interactions/day)
- Offline capture is primary use case
- Notes may be long-form text

**Recommended approach:**
```python
# apps/snowball/models.py

class Contact(FieldLevelLWWMixin, SyncableModel):
    """
    Contact with field-level LWW conflict resolution.

    Uses FieldLevelLWWMixin for per-field timestamps.
    """
    PREFIX = 'ct_'

    name = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)

    # field_timestamps inherited from FieldLevelLWWMixin

    class Meta(SyncableModel.Meta):
        conflict_strategy = 'lww_field'


class Interaction(SyncableModel):
    PREFIX = 'int_'

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=32)  # meeting, call, email, note
    content = models.TextField()  # Could use CRDT for collaborative editing
    occurred_at = models.DateTimeField()
    location = models.JSONField(null=True)  # {lat, lng, name}

    class Meta(SyncableModel.Meta):
        conflict_strategy = 'append_only'  # Never overwrite, just add
```

### 6.2 Toggl-like (Time Tracking)

**Entities to sync:**
- `TimeEntry` - project_id, description, start_time, end_time, tags, billable
- `Project` - name, color, client_id, billable_rate
- `Client` - name

**Sync characteristics:**
- High write frequency (running timer updates every minute)
- Field-level accuracy critical (duration, billable status)
- Overlapping entries must be validated

**Recommended approach:**
```python
# apps/timetracker/models.py

class TimeEntry(SyncableModel):
    PREFIX = 'te_'

    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True)
    description = models.CharField(max_length=500, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)  # Null = running
    tags = models.JSONField(default=list)
    billable = models.BooleanField(default=False)

    # Running timer state
    is_running = models.BooleanField(default=False)

    class Meta(SyncableModel.Meta):
        conflict_strategy = 'lww_with_validation'

    def validate_no_overlap(self):
        """Server-side validation: no overlapping entries."""
        overlapping = TimeEntry.objects.filter(
            workspace=self.workspace,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(id=self.id)

        if overlapping.exists():
            raise ValidationError('TIME_ENTRY_OVERLAP')
```

### 6.3 Generic B2B Platform

**Design for extensibility:**
```python
# apps/sync/registry.py

class SyncRegistry:
    """Registry of syncable entity types and their strategies."""

    _entities: dict[str, type[SyncableModel]] = {}
    _strategies: dict[str, ConflictStrategy] = {}

    @classmethod
    def register(cls, entity_type: str, model: type[SyncableModel], strategy: str = 'lww'):
        cls._entities[entity_type] = model
        cls._strategies[entity_type] = STRATEGIES[strategy]

    @classmethod
    def resolve_conflict(cls, entity_type: str, server: SyncableModel, client_data: dict) -> SyncResult:
        strategy = cls._strategies.get(entity_type, STRATEGIES['lww'])
        return strategy.resolve(server, client_data)

# In app startup
SyncRegistry.register('contact', Contact, 'lww_field')
SyncRegistry.register('time_entry', TimeEntry, 'lww_with_validation')
SyncRegistry.register('note', Note, 'crdt_text')
```

---

## 7. Integration with Existing Infrastructure

### 7.1 Event Flow

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

### 7.2 Webhook Events for Sync

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

### 7.3 Rate Limiting

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

### 7.4 Server-Side Mutations and Sync Stream

**Critical**: Any server-side mutation that should propagate to clients **must** update the entity's `updated_at` timestamp to enter the sync stream.

#### Safe Patterns

```python
# ✅ CORRECT: Model.save() updates updated_at automatically
def archive_old_contacts():
    """Background job: archive contacts not updated in 1 year."""
    cutoff = timezone.now() - timedelta(days=365)
    for contact in Contact.objects.filter(updated_at__lt=cutoff):
        contact.status = 'archived'
        contact.save()  # ✅ updated_at updated, enters sync stream

# ✅ CORRECT: Explicit updated_at in bulk update
def bulk_reassign_contacts(old_owner_id: int, new_owner_id: int):
    """Admin action: reassign all contacts."""
    Contact.objects.filter(owner_id=old_owner_id).update(
        owner_id=new_owner_id,
        updated_at=timezone.now(),  # ✅ Explicit
    )

# ✅ CORRECT: Custom manager method that ensures sync visibility
class SyncableManager(SoftDeleteAllManager):
    def bulk_update_for_sync(self, queryset, **updates):
        """Bulk update that ensures changes enter sync stream."""
        updates['updated_at'] = timezone.now()
        return queryset.update(**updates)
```

#### Dangerous Patterns (Will Not Sync)

```python
# ❌ WRONG: Direct update bypasses updated_at
Contact.objects.filter(status='pending').update(status='active')
# Clients will NEVER see this change!

# ❌ WRONG: Raw SQL without updated_at
with connection.cursor() as cursor:
    cursor.execute("UPDATE contacts SET status = 'active' WHERE ...")
# Clients will NEVER see this change!

# ❌ WRONG: F() expressions without updated_at
Contact.objects.filter(id=1).update(view_count=F('view_count') + 1)
# Clients will NEVER see this change!
```

#### Checklist for Server-Side Mutations

| Source | Action Required |
|--------|-----------------|
| Management commands | Use `.save()` or explicit `updated_at` |
| Celery/background tasks | Use `.save()` or explicit `updated_at` |
| Admin panel actions | Use `.save()` or explicit `updated_at` |
| Webhook handlers | Use `.save()` or explicit `updated_at` |
| Database triggers | Include `updated_at = NOW()` |
| Data migrations | Include `updated_at` in UPDATE |

#### Linting/CI Recommendation

Consider adding a custom linter rule or pre-commit hook that warns on `.update()` calls to syncable models without explicit `updated_at`:

```python
# Example: Custom Django check
from django.core.checks import Warning, register

@register()
def check_sync_update_patterns(app_configs, **kwargs):
    """Warn about .update() without updated_at on syncable models."""
    # Implementation would scan code for patterns like:
    # SyncableModel.objects.filter(...).update(...) without updated_at
    ...
```

---

## 8. Scalability Considerations

### Current Scale (Phase 1)
- 1,000-10,000 workspaces
- 10-50 users per workspace
- Django on ECS handles comfortably

### Future Scale (Phase 2)

Based on escape hatches from the architecture docs:

```
High-volume ingestion (>10k concurrent syncing users):

Before: Mobile → Django → PostgreSQL
After:  Mobile → API Gateway → Lambda → PostgreSQL
                     ↓
              SQS (buffer spikes)
```

### Database Optimizations

```sql
-- Composite index for pull queries
-- IMPORTANT: No partial index - we need ALL records including soft-deleted
CREATE INDEX idx_syncable_pull ON {entity_table}
    (workspace_id, updated_at, id);

-- Index for tombstone cleanup job
CREATE INDEX idx_syncable_tombstones ON {entity_table}
    (deleted_at)
    WHERE deleted_at IS NOT NULL;

-- Partition sync_operations by month for large deployments
CREATE TABLE sync_operations (
    ...
) PARTITION BY RANGE (server_timestamp);
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Core Sync Protocol)
1. Create `SyncableModel` base class
2. Implement `SyncOperation` log model
3. Build `/sync/push` and `/sync/pull` endpoints
4. Add cursor-based pagination
5. Implement LWW conflict resolution
6. Integrate with existing event outbox

### Phase 2: Use Case Implementation
1. Define Snowball models (Contact, Interaction)
2. Define TimeTracker models (TimeEntry, Project)
3. Implement use-case-specific validation rules
4. Build TypeScript/React Native sync client SDK

### Phase 3: Advanced Features
1. Field-level conflict resolution
2. CRDT support for rich text (Yjs integration)
3. Real-time push via WebSockets (optional)
4. Conflict UI for manual resolution

### Phase 4: Scale & Optimize
1. Lambda-based ingestion for high volume
2. Read replicas for pull queries
3. Operational metrics and alerting
4. Snapshot/compaction for CRDT data

---

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ID format | ULIDs | Time-sortable, collision-free, works offline |
| Cursor format | `{timestamp}_{id}` | Monotonic, resumable, stable ordering |
| Default conflict strategy | LWW (field-level) | Simple, covers 90% of cases |
| CRDT library | Yjs (if needed) | Mature, well-documented, TypeScript-native |
| Sync transport | HTTPS REST | Simple, works everywhere, cacheable |
| Real-time (future) | WebSocket for presence only | Sync still via REST for reliability |

---

## References

- [Lessons from implementing a sync engine](https://www.sandromaglione.com/newsletter/lessons-from-implementing-a-sync-engine)
- [Local-First Apps in 2025: CRDTs, Replication Patterns](https://debugg.ai/resources/local-first-apps-2025-crdts-replication-edge-storage-offline-sync)
- [Best CRDT Libraries 2025](https://velt.dev/blog/best-crdt-libraries-real-time-data-sync)
- [Offline-First Architecture: Designing for Reality](https://medium.com/@jusuftopic/offline-first-architecture-designing-for-reality-not-just-the-cloud-e5fd18e50a79)
- [Offline-First Done Right: Sync Patterns](https://developersvoice.com/blog/mobile/offline-first-sync-patterns/)
- [Android Offline-First Architecture Guide](https://developer.android.com/topic/architecture/data-layer/offline-first)
- [OT vs CRDT for Collaborative Interfaces](https://dev.to/puritanic/building-collaborative-interfaces-operational-transforms-vs-crdts-2obo)
- [Real-time collaboration: OT vs CRDT](https://www.tiny.cloud/blog/real-time-collaboration-ot-vs-crdt/)
- [The CRDT Dictionary](https://www.iankduncan.com/engineering/2025-11-27-crdt-dictionary/)
