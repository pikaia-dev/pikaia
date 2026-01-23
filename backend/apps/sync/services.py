"""
Sync engine services.

Core business logic for processing sync operations and fetching changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.logging import get_logger
from apps.sync.cursor import encode_cursor, parse_cursor
from apps.sync.exceptions import UnknownEntityTypeError
from apps.sync.models import FieldLevelLWWMixin, SyncableModel, SyncOperation
from apps.sync.registry import SyncRegistry
from apps.sync.schemas import ChangeOut, SyncOperationIn, SyncResultOut, SyncStatus

if TYPE_CHECKING:
    from apps.accounts.models import Member
    from apps.organizations.models import Organization

logger = get_logger(__name__)

# Clock skew tolerance for pull queries (covers typical NTP drift)
CLOCK_SKEW_TOLERANCE = timedelta(
    milliseconds=getattr(settings, "SYNC_CLOCK_SKEW_TOLERANCE_MS", 100)
)


@dataclass
class SyncResult:
    """Result of processing a sync operation."""

    status: SyncStatus
    server_timestamp: datetime
    server_version: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict | None = None
    conflict_data: dict | None = None
    conflict_fields: list[str] | None = None


def process_sync_operation(
    organization: Organization,
    actor: Member,
    operation: SyncOperationIn,
    device_id: str,
) -> SyncResult:
    """
    Process a single sync operation.

    Handles idempotency via atomic claim pattern using unique constraint.

    Args:
        organization: The organization context
        actor: The member performing the operation
        operation: The operation to process
        device_id: The device ID from the request

    Returns:
        SyncResult with status and details
    """
    now = timezone.now()

    # 1. Get the model class for this entity type
    try:
        model = SyncRegistry.get_model(operation.entity_type)
    except UnknownEntityTypeError:
        return SyncResult(
            status="rejected",
            server_timestamp=now,
            error_code="UNKNOWN_ENTITY_TYPE",
            error_message=f"Unknown entity type: {operation.entity_type}",
        )

    # 2. Calculate drift for observability
    drift_ms = int((now - operation.client_timestamp).total_seconds() * 1000)

    # 3. Atomically claim the idempotency key by creating the log record first
    try:
        with transaction.atomic():
            sync_op = SyncOperation.objects.create(
                idempotency_key=operation.idempotency_key,
                organization=organization,
                actor=actor,
                device_id=device_id,
                entity_type=operation.entity_type,
                entity_id=operation.entity_id,
                intent=operation.intent,
                payload=operation.data,
                client_timestamp=operation.client_timestamp,
                status=SyncOperation.Status.PENDING,
                drift_ms=drift_ms,
                client_retry_count=operation.retry_count,
            )
    except IntegrityError:
        # Unique constraint violation = duplicate idempotency_key
        logger.debug(
            "sync_operation_duplicate",
            idempotency_key=operation.idempotency_key,
        )
        return SyncResult(
            status="duplicate",
            server_timestamp=now,
        )

    # 4. Process the operation based on intent
    try:
        if operation.intent == "create":
            entity = _process_create(
                model=model,
                organization=organization,
                actor=actor,
                device_id=device_id,
                entity_id=operation.entity_id,
                data=operation.data,
                client_timestamp=operation.client_timestamp,
            )
            result = SyncResult(
                status="applied",
                server_timestamp=entity.updated_at,
                server_version=entity.sync_version,
            )

        elif operation.intent == "update":
            entity, conflict_fields = _process_update(
                model=model,
                organization=organization,
                actor=actor,
                device_id=device_id,
                entity_id=operation.entity_id,
                data=operation.data,
                client_timestamp=operation.client_timestamp,
                base_version=operation.base_version,
            )
            result = SyncResult(
                status="applied",
                server_timestamp=entity.updated_at,
                server_version=entity.sync_version,
                conflict_fields=conflict_fields,
            )

        elif operation.intent == "delete":
            _process_delete(
                model=model,
                organization=organization,
                entity_id=operation.entity_id,
            )
            result = SyncResult(
                status="applied",
                server_timestamp=now,
            )

        else:
            result = SyncResult(
                status="rejected",
                server_timestamp=now,
                error_code="INVALID_INTENT",
                error_message=f"Invalid intent: {operation.intent}",
            )

        # Mark operation as applied
        sync_op.status = SyncOperation.Status.APPLIED
        sync_op.conflict_fields = result.conflict_fields
        sync_op.save(update_fields=["status", "conflict_fields"])

        logger.info(
            "sync_operation_applied",
            idempotency_key=operation.idempotency_key,
            entity_type=operation.entity_type,
            entity_id=operation.entity_id,
            intent=operation.intent,
        )

        return result

    except ObjectDoesNotExist:
        sync_op.status = SyncOperation.Status.REJECTED
        sync_op.resolution_details = {"error": "NOT_FOUND"}
        sync_op.save(update_fields=["status", "resolution_details"])
        return SyncResult(
            status="rejected",
            server_timestamp=now,
            error_code="NOT_FOUND",
            error_message=f"Entity {operation.entity_id} not found",
        )

    except PermissionDenied as e:
        sync_op.status = SyncOperation.Status.REJECTED
        sync_op.resolution_details = {"error": "FORBIDDEN"}
        sync_op.save(update_fields=["status", "resolution_details"])
        return SyncResult(
            status="rejected",
            server_timestamp=now,
            error_code="FORBIDDEN",
            error_message=str(e) or "Permission denied",
        )

    except ValidationError as e:
        sync_op.status = SyncOperation.Status.REJECTED
        sync_op.resolution_details = {"error": "VALIDATION_ERROR", "details": str(e)}
        sync_op.save(update_fields=["status", "resolution_details"])
        return SyncResult(
            status="rejected",
            server_timestamp=now,
            error_code="VALIDATION_ERROR",
            error_message="Validation failed",
            error_details=e.message_dict if hasattr(e, "message_dict") else {"__all__": [str(e)]},
        )

    except Exception as e:
        logger.exception(
            "sync_operation_error",
            idempotency_key=operation.idempotency_key,
            error=str(e),
        )
        sync_op.status = SyncOperation.Status.REJECTED
        sync_op.resolution_details = {"error": "INTERNAL_ERROR", "message": str(e)}
        sync_op.save(update_fields=["status", "resolution_details"])
        raise


def _process_create(
    model: type[SyncableModel],
    organization: Organization,
    actor: Member,
    device_id: str,
    entity_id: str,
    data: dict,
    client_timestamp: datetime,
) -> SyncableModel:
    """Process a create operation."""
    # Check if entity already exists (idempotent create)
    existing = model.all_objects.filter(
        id=entity_id,
        organization=organization,
    ).first()

    if existing:
        # Entity already exists - treat as update if not deleted
        if existing.deleted_at:
            # Restore and update
            existing.deleted_at = None
        for field, value in data.items():
            if hasattr(existing, field):
                setattr(existing, field, value)
        existing.last_modified_by = actor
        existing.device_id = device_id
        if isinstance(existing, FieldLevelLWWMixin):
            for field in data:
                existing.set_field_timestamp(field, client_timestamp)
        existing.save()
        return existing

    # Create new entity
    create_kwargs = {
        "id": entity_id,
        "organization": organization,
        "last_modified_by": actor,
        "device_id": device_id,
    }

    # Add data fields
    for field, value in data.items():
        if hasattr(model, field) or field in [f.name for f in model._meta.get_fields()]:
            create_kwargs[field] = value

    entity = model(**create_kwargs)

    # Set field timestamps for LWW models
    if isinstance(entity, FieldLevelLWWMixin):
        for field in data:
            entity.set_field_timestamp(field, client_timestamp)

    entity.save()
    return entity


def _process_update(
    model: type[SyncableModel],
    organization: Organization,
    actor: Member,
    device_id: str,
    entity_id: str,
    data: dict,
    client_timestamp: datetime,
    base_version: int | None = None,
) -> tuple[SyncableModel, list[str] | None]:
    """
    Process an update operation with field-level LWW.

    Returns:
        Tuple of (entity, conflict_fields) where conflict_fields lists
        fields that were rejected due to LWW.
    """
    entity = model.objects.get(id=entity_id, organization=organization)

    # Optional version check for optimistic concurrency
    if base_version is not None and entity.sync_version != base_version:
        raise ValidationError(
            f"Version mismatch: expected {base_version}, got {entity.sync_version}"
        )

    conflict_fields: list[str] | None = None

    # Apply field-level LWW if model supports it
    if isinstance(entity, FieldLevelLWWMixin):
        applied, rejected = apply_field_level_lww(entity, data, client_timestamp)
        if rejected:
            conflict_fields = list(rejected.keys())
    else:
        # Simple LWW - apply all fields
        for field, value in data.items():
            if hasattr(entity, field):
                setattr(entity, field, value)

    entity.last_modified_by = actor
    entity.device_id = device_id
    entity.save()

    return entity, conflict_fields


def _process_delete(
    model: type[SyncableModel],
    organization: Organization,
    entity_id: str,
) -> None:
    """Process a delete operation (soft delete)."""
    entity = model.objects.get(id=entity_id, organization=organization)
    entity.soft_delete()


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
        - rejected_fields: {field: {client_value, server_value, ...}} that were rejected
    """
    applied: dict[str, Any] = {}
    rejected: dict[str, dict[str, Any]] = {}

    for field, client_value in client_data.items():
        # Skip non-syncable fields
        if field in FieldLevelLWWMixin.LWW_EXCLUDED_FIELDS:
            continue

        if not hasattr(entity, field):
            continue

        server_value = getattr(entity, field, None)
        server_ts = entity.get_field_timestamp(field)

        # Client wins if:
        # 1. Server has no timestamp for this field (new field or migration)
        # 2. Client timestamp is newer than server timestamp
        if server_ts is None or client_timestamp > server_ts:
            setattr(entity, field, client_value)
            entity.set_field_timestamp(field, client_timestamp)
            applied[field] = client_value
        else:
            # Server wins - field was modified more recently
            if client_value != server_value:
                rejected[field] = {
                    "client_value": client_value,
                    "client_timestamp": client_timestamp.isoformat(),
                    "server_value": server_value,
                    "server_timestamp": server_ts.isoformat(),
                }

    return applied, rejected


def fetch_changes_for_pull(
    organization: Organization,
    entity_types: list[str] | None,
    since_cursor: str | None,
    limit: int,
) -> tuple[list[ChangeOut], str | None, bool]:
    """
    Fetch changes for a pull request.

    Args:
        organization: The organization to fetch changes for
        entity_types: Optional list of entity types to filter
        since_cursor: Optional cursor from previous pull
        limit: Maximum number of changes to return

    Returns:
        Tuple of (changes, next_cursor, has_more)
    """
    cursor = parse_cursor(since_cursor)

    # Determine which entity types to query
    if entity_types:
        types_to_query = [t for t in entity_types if SyncRegistry.is_registered(t)]
    else:
        types_to_query = SyncRegistry.get_all_entity_types()

    if not types_to_query:
        return [], since_cursor, False

    # Collect changes from all entity types
    all_changes: list[tuple[datetime, str, str, SyncableModel]] = []

    for entity_type in types_to_query:
        model = SyncRegistry.get_model(entity_type)

        # MUST use all_objects to include soft-deleted records
        qs = model.all_objects.filter(organization=organization)

        if cursor:
            # Use strict cursor comparison for pagination
            # Records with updated_at > cursor OR (updated_at == cursor AND id > cursor)
            qs = qs.filter(
                models.Q(updated_at__gt=cursor.timestamp)
                | models.Q(updated_at=cursor.timestamp, id__gt=cursor.entity_id)
            )

        # Order by updated_at and id for stable pagination
        qs = qs.order_by("updated_at", "id")

        for entity in qs[: limit + 1]:
            all_changes.append((entity.updated_at, entity.id, entity_type, entity))

    # Sort all changes across entity types
    all_changes.sort(key=lambda x: (x[0], x[1]))

    # Check if there are more results
    has_more = len(all_changes) > limit
    changes_to_return = all_changes[:limit]

    # Build response
    changes: list[ChangeOut] = []
    for _updated_at, entity_id, entity_type, entity in changes_to_return:
        is_deleted = entity.deleted_at is not None

        change = ChangeOut(
            entity_type=entity_type,
            entity_id=entity_id,
            operation="delete" if is_deleted else "upsert",
            data=_serialize_entity(entity_type, entity) if not is_deleted else None,
            version=entity.sync_version,
            updated_at=entity.updated_at,
        )
        changes.append(change)

    # Generate next cursor from last change
    # If no changes, return the input cursor to maintain position
    next_cursor: str | None
    if changes_to_return:
        last_change = changes_to_return[-1]
        next_cursor = encode_cursor(last_change[0], last_change[1])
    else:
        next_cursor = since_cursor  # Return input cursor if no new changes

    return changes, next_cursor, has_more


def _serialize_entity(entity_type: str, entity: SyncableModel) -> dict:
    """Serialize an entity to a dict for the API response."""
    # Check for custom serializer
    serializer = SyncRegistry.get_serializer(entity_type)
    if serializer:
        return serializer(entity)

    # Default serialization - include all concrete fields except excluded ones
    excluded = {
        "organization",
        "organization_id",
        "last_modified_by",
        "last_modified_by_id",
        "deleted_at",
    }

    result = {}
    for field in entity._meta.get_fields():
        if not field.concrete:
            continue
        if field.name in excluded:
            continue
        if field.is_relation:
            # For FKs, include the ID
            value = getattr(entity, f"{field.name}_id", None)
            if value is not None:
                result[f"{field.name}_id"] = str(value)
        else:
            value = getattr(entity, field.name, None)
            if value is not None:
                # Handle datetime serialization
                if isinstance(value, datetime):
                    result[field.name] = value.isoformat()
                else:
                    result[field.name] = value

    return result


def to_sync_result_out(result: SyncResult, idempotency_key: str) -> SyncResultOut:
    """Convert a SyncResult to API response schema."""
    return SyncResultOut(
        idempotency_key=idempotency_key,
        status=result.status,
        server_timestamp=result.server_timestamp,
        server_version=result.server_version,
        error_code=result.error_code,
        error_message=result.error_message,
        error_details=result.error_details,
        conflict_data=result.conflict_data,
    )
