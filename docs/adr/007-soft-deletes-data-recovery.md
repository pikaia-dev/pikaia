# ADR 007: Soft Deletes for Data Recovery and Referential Integrity

**Date:** January 18, 2026

## Context

We need to decide how to handle record deletion for:
- Organizations (tenants)
- Members (users within organizations)
- Other business entities

Key requirements:
- Recover accidentally deleted data
- Maintain foreign key references (e.g., `invoice.member` after member deletion)
- Sync with Stytch's webhook-driven lifecycle
- Support GDPR "right to deletion" when required

**Note:** Audit trail requirements are handled separately by our event sourcing system (see ADR 002). The AuditLog captures *what happened* ("member.deleted at X by Y"). Soft deletes preserve *the entity data itself*.

Options considered:
1. **Hard deletes** - Simple, but data is gone forever, breaks FK references
2. **Soft deletes** - Mark as deleted, filter by default, preserve data
3. **Archive tables** - Copy before delete, sync complexity

## Decision

Use **soft deletes** with `deleted_at` timestamps for Organization and Member models. Provide both filtered and unfiltered managers.

## Rationale

### Data Recovery

Soft deletes enable restoration of accidentally deleted records:
- Admin deletes wrong member → restore by clearing `deleted_at`
- No need to reconstruct from event history
- Immediate recovery without data loss

### Referential Integrity

Foreign keys remain valid after soft delete:
```python
# Hard delete breaks this:
invoice.member  # DoesNotExist error

# Soft delete preserves it:
invoice.member  # Returns the member
invoice.member.deleted_at  # Shows when they were deleted
```

This is critical for:
- Billing records referencing deleted members
- Audit queries joining across tables
- Historical reporting

### Complements Event Sourcing

Our architecture separates concerns:

| System | Purpose | Data |
|--------|---------|------|
| **AuditLog** (events) | What happened | Event type, actor, timestamp |
| **Soft deletes** | Entity preservation | Full entity state, recoverable |

Events tell you "member X was deleted by admin Y at time Z."
Soft deletes let you query "what was member X's email and role?"

### Stytch Webhook Alignment

Our data syncs from Stytch webhooks:
```python
@webhook_handler("member.deleted")
def handle_member_deleted(event_data):
    # Stytch tells us member was deleted
    # We soft-delete locally to maintain sync
    Member.all_objects.filter(stytch_member_id=event_data["member_id"]).update(
        deleted_at=timezone.now()
    )
```

Soft deletes match the webhook-driven lifecycle.

### Clean API Without Deleted Records

Default manager filters out deleted records automatically:
```python
# Normal queries see only active records
members = Member.objects.filter(organization=org)  # Excludes deleted

# Audit/admin queries can access everything
all_members = Member.all_objects.filter(organization=org)  # Includes deleted
```

Business logic doesn't need to remember `deleted_at__isnull=True` everywhere.

### Referential Integrity Preserved

Foreign keys remain valid after soft delete:
```python
# Old approach: CASCADE delete loses audit history
# Soft delete: References stay valid, can trace relationships

# Invoice still references the Member who placed it
invoice.member  # Works even if member is soft-deleted
invoice.member.deleted_at  # Shows when they were deleted
```

## Consequences

### Positive
- **Recoverability** - Undo accidental deletions easily
- **FK integrity** - References to deleted entities remain valid
- **Query safety** - Default manager protects business logic
- **Webhook compatibility** - Matches Stytch's deletion events

### Negative
- **Data growth** - Deleted records consume storage
- **Query complexity** - Must use correct manager for each use case
- **Unique constraints** - Can't use simple unique constraints on soft-deleted fields
- **Actual deletion** - Need separate process for GDPR "right to deletion"

### Mitigations
- Periodic cleanup job for old soft-deleted records (e.g., 90 days)
- Clear naming: `objects` vs `all_objects` managers
- Partial unique indexes exclude deleted records
- Hard delete function for GDPR compliance when required

## Implementation Notes

### Model Pattern
```python
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

class AllObjectsManager(models.Manager):
    pass  # No filtering

class Organization(models.Model):
    # Fields
    name = models.CharField(max_length=255)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Managers
    objects = SoftDeleteManager()  # Default: excludes deleted
    all_objects = AllObjectsManager()  # Admin: includes deleted

    class Meta:
        # Unique constraint only for active records
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_org_slug",
            )
        ]

    def delete(self, *args, **kwargs):
        """Soft delete by default."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self):
        """Actual deletion for GDPR compliance."""
        super().delete()
```

### Query Examples
```python
# Normal business logic - automatically filtered
active_orgs = Organization.objects.all()
org = Organization.objects.get(slug="acme")

# Admin/audit access - see everything
all_orgs = Organization.all_objects.all()
deleted_orgs = Organization.all_objects.filter(deleted_at__isnull=False)

# Recovery
org = Organization.all_objects.get(id=org_id)
org.deleted_at = None
org.save()
```

### Webhook Handling
```python
@webhook_handler("organization.deleted")
def handle_org_deleted(payload: StytchWebhookPayload):
    """
    Stytch notifies us of org deletion.
    Soft delete locally to maintain sync state.
    """
    org = Organization.all_objects.filter(
        stytch_org_id=payload.data["organization_id"]
    ).first()

    if org and not org.deleted_at:
        org.deleted_at = timezone.now()
        org.save(update_fields=["deleted_at"])

        # Also soft-delete all members
        Member.all_objects.filter(
            organization=org,
            deleted_at__isnull=True,
        ).update(deleted_at=timezone.now())
```

### Cleanup Job
```python
# management/commands/cleanup_deleted.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        """Hard delete records soft-deleted more than 90 days ago."""
        cutoff = timezone.now() - timedelta(days=90)

        # Delete in correct order (respect FK constraints)
        Member.all_objects.filter(deleted_at__lt=cutoff).delete()
        Organization.all_objects.filter(deleted_at__lt=cutoff).delete()
```

### Models Using Soft Deletes
| Model | Soft Delete | Rationale |
|-------|-------------|-----------|
| Organization | Yes | Tenant data, audit trail |
| Member | Yes | User data, synced from Stytch |
| User | Yes | Cross-org identity |
| Subscription | No | Stripe is source of truth |
| OutboxEvent | No | Transient, cleaned after publish |
| AuditLog | No | Permanent record |
