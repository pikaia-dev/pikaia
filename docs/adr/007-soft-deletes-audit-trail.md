# ADR 007: Soft Deletes for Audit Trail and Compliance

**Status:** Accepted
**Date:** January 18, 2026

## Context

B2B SaaS applications face compliance requirements:
- Data retention policies (GDPR, SOC 2)
- Audit trails for enterprise customers
- Ability to recover accidentally deleted data
- Legal hold requirements

We need to decide how to handle record deletion for:
- Organizations (tenants)
- Members (users within organizations)
- Other business entities

Options considered:
1. **Hard deletes** - Simple, but data is gone forever
2. **Soft deletes** - Mark as deleted, filter by default
3. **Event sourcing** - Full history, major complexity
4. **Archive tables** - Copy before delete, sync complexity

## Decision

Use **soft deletes** with `deleted_at` timestamps for Organization and Member models. Provide both filtered and unfiltered managers.

## Rationale

### Compliance Ready

Soft deletes enable:
- **Audit trail**: Know what was deleted and when
- **Data recovery**: Undo accidental deletions
- **Legal holds**: Preserve data during investigations
- **GDPR compliance**: Can perform actual deletion when required

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
- **Audit compliance** - Full history of what existed
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
