"""
Sync API endpoints.

Provides push and pull endpoints for offline-first sync.
"""

from django.conf import settings
from django.http import HttpRequest
from ninja import Query, Router
from ninja.errors import HttpError

from apps.core.logging import get_logger
from apps.core.security import BearerAuth, get_auth_context
from apps.events.services import publish_event
from apps.sync.exceptions import CursorInvalidError
from apps.sync.registry import SyncRegistry
from apps.sync.schemas import (
    SyncPullParams,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncResultOut,
)
from apps.sync.services import (
    fetch_changes_for_pull,
    process_sync_operation,
    to_sync_result_out,
)

logger = get_logger(__name__)

router = Router(tags=["sync"])
bearer_auth = BearerAuth()


@router.post(
    "/push",
    response=SyncPushResponse,
    auth=bearer_auth,
    summary="Push sync operations",
    description="Push a batch of sync operations from client to server. Max 100 operations per batch.",
)
def sync_push(request: HttpRequest, payload: SyncPushRequest) -> SyncPushResponse:
    """
    Process a batch of sync operations.

    Each operation is processed independently. Results are returned in the same
    order as the input operations.
    """
    user, member, organization = get_auth_context(request)

    max_batch_size = getattr(settings, "SYNC_PUSH_MAX_BATCH_SIZE", 100)
    if len(payload.operations) > max_batch_size:
        raise HttpError(400, f"Maximum {max_batch_size} operations per batch")

    results: list[SyncResultOut] = []

    for op in payload.operations:
        result = process_sync_operation(
            organization=organization,
            actor=member,
            operation=op,
            device_id=payload.device_id,
        )

        results.append(to_sync_result_out(result, op.idempotency_key))

        # Emit event for webhooks/integrations on successful apply
        if result.status == "applied" and op.intent != "delete":
            try:
                model = SyncRegistry.get_model(op.entity_type)
                entity = model.all_objects.filter(id=op.entity_id).first()
                if entity:
                    publish_event(
                        event_type=f"{op.entity_type}.synced",
                        aggregate=entity,
                        data={"intent": op.intent, **op.data},
                        actor=user,
                        organization_id=str(organization.id),
                    )
            except Exception as e:
                # Don't fail the sync if event publishing fails
                logger.warning(
                    "sync_event_publish_failed",
                    entity_type=op.entity_type,
                    entity_id=op.entity_id,
                    error=str(e),
                )

    logger.info(
        "sync_push_completed",
        device_id=payload.device_id,
        operation_count=len(payload.operations),
        applied_count=sum(1 for r in results if r.status == "applied"),
    )

    return SyncPushResponse(results=results)


@router.get(
    "/pull",
    response=SyncPullResponse,
    auth=bearer_auth,
    summary="Pull sync changes",
    description="Pull changes from server since the given cursor. Returns paginated results.",
)
def sync_pull(request: HttpRequest, params: Query[SyncPullParams]) -> SyncPullResponse:
    """
    Fetch changes since the cursor.

    The cursor is opaque - clients should not parse or modify it.
    Pass the returned cursor to subsequent calls to paginate.
    """
    user, member, organization = get_auth_context(request)

    # Parse entity types filter
    entity_types = None
    if params.entity_types:
        entity_types = [t.strip() for t in params.entity_types.split(",") if t.strip()]

    # Apply limits
    default_limit = getattr(settings, "SYNC_PULL_DEFAULT_LIMIT", 100)
    max_limit = getattr(settings, "SYNC_PULL_MAX_LIMIT", 500)
    limit = min(params.limit or default_limit, max_limit)

    try:
        changes, next_cursor, has_more = fetch_changes_for_pull(
            organization=organization,
            entity_types=entity_types,
            since_cursor=params.since,
            limit=limit,
        )
    except CursorInvalidError:
        raise HttpError(400, "Invalid cursor. Client should perform full resync.") from None

    logger.info(
        "sync_pull_completed",
        since_cursor=params.since is not None,
        entity_types=entity_types,
        change_count=len(changes),
        has_more=has_more,
    )

    return SyncPullResponse(
        changes=changes,
        cursor=next_cursor,
        has_more=has_more,
        force_resync=False,
    )
