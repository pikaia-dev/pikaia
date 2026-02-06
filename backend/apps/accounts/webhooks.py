"""
Stytch webhook handler.

Handles incoming webhooks from Stytch for member and organization events.
Stytch uses Svix for webhook delivery and signature verification.
"""

import json
from datetime import UTC, datetime

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from svix.webhooks import Webhook, WebhookVerificationError

from apps.accounts.models import Member
from apps.accounts.services import get_or_create_member_from_stytch, get_or_create_user_from_stytch
from apps.core.logging import get_logger
from apps.core.webhooks import mark_webhook_processed
from apps.events.services import publish_event
from apps.organizations.models import Organization
from config.settings.base import settings

logger = get_logger(__name__)


def handle_member_created(data: dict) -> None:
    """
    Handle member.create event from Stytch.

    Creates the member in local database if it doesn't exist.
    This handles the case where Django creation failed after Stytch succeeded.
    """
    member_data = data.get("member", {})
    stytch_member_id = member_data.get("member_id")
    stytch_org_id = member_data.get("organization_id")
    email = member_data.get("email_address")

    if not all([stytch_member_id, stytch_org_id, email]):
        logger.warning(
            "stytch_webhook_member_create_missing_fields",
            member_id=stytch_member_id,
            org_id=stytch_org_id,
            email=email,
        )
        return

    # Check if member already exists (normal case - sync already worked)
    if Member.all_objects.filter(stytch_member_id=stytch_member_id).exists():
        logger.debug("stytch_webhook_member_exists", stytch_member_id=stytch_member_id)
        return

    # Check if organization exists
    try:
        org = Organization.objects.get(stytch_org_id=stytch_org_id)
    except Organization.DoesNotExist:
        logger.warning(
            "stytch_webhook_org_not_found_for_member",
            stytch_org_id=stytch_org_id,
            stytch_member_id=stytch_member_id,
        )
        return

    # Determine role from Stytch RBAC
    roles = member_data.get("roles", [])
    role = "member"
    for r in roles:
        if isinstance(r, dict) and r.get("role_id") == "stytch_admin":
            role = "admin"
            break

    # Get or create user and member
    logger.info(
        "stytch_webhook_member_creating",
        stytch_member_id=stytch_member_id,
        email=email,
        org_name=org.name,
    )
    user = get_or_create_user_from_stytch(
        email=email,
        name=member_data.get("name", ""),
    )
    member = get_or_create_member_from_stytch(
        user=user,
        organization=org,
        stytch_member_id=stytch_member_id,
        role=role,
    )

    # Emit member.created event (system actor - webhook triggered)
    publish_event(
        event_type="member.created",
        aggregate=member,
        data={
            "email": email,
            "role": role,
            "created_via": "stytch_webhook",
        },
        actor=None,  # System/webhook event
    )


def handle_member_updated(data: dict) -> None:
    """
    Handle member.update event from Stytch.

    Updates member role and status from Stytch data.
    """
    member_data = data.get("member", {})
    stytch_member_id = member_data.get("member_id")

    if not stytch_member_id:
        logger.warning("stytch_webhook_member_update_missing_id")
        return

    try:
        member = Member.objects.select_related("user").get(stytch_member_id=stytch_member_id)
    except Member.DoesNotExist:
        logger.info("stytch_webhook_member_not_found", stytch_member_id=stytch_member_id)
        return

    # Update role from Stytch RBAC
    roles = member_data.get("roles", [])
    new_role = "member"  # Default
    for role in roles:
        if role.get("role_id") == "stytch_admin":
            new_role = "admin"
            break

    # Update member fields
    updated = False
    if member.role != new_role:
        logger.info(
            "stytch_webhook_member_role_updated",
            stytch_member_id=stytch_member_id,
            old_role=member.role,
            new_role=new_role,
        )
        member.role = new_role
        updated = True

    # Check for status changes (deactivated via SCIM, etc.)
    status = member_data.get("status")
    if status == "deleted" and member.deleted_at is None:
        logger.info("stytch_webhook_member_deleted", stytch_member_id=stytch_member_id)
        member.deleted_at = datetime.now(UTC)
        updated = True

    if updated:
        member.save()


def handle_member_deleted(data: dict) -> None:
    """
    Handle member.delete event from Stytch.

    Soft deletes the member in local database.
    """
    member_id = data.get("id") or data.get("member", {}).get("member_id")

    if not member_id:
        logger.warning("stytch_webhook_member_delete_missing_id")
        return

    try:
        member = Member.objects.select_related("user").get(stytch_member_id=member_id)
    except Member.DoesNotExist:
        logger.debug("stytch_webhook_member_already_deleted", stytch_member_id=member_id)
        return

    if member.deleted_at is None:
        logger.info("stytch_webhook_member_soft_delete", stytch_member_id=member_id)
        email = member.user.email if member.user else "unknown"
        member.soft_delete()

        # Emit member.removed event (system actor - webhook triggered)
        publish_event(
            event_type="member.removed",
            aggregate=member,
            data={
                "email": email,
                "removed_via": "stytch_webhook",
            },
            actor=None,  # System/webhook event
        )


def handle_organization_updated(data: dict) -> None:
    """
    Handle organization.update event from Stytch.

    Syncs organization name and slug changes.
    """
    org_data = data.get("organization", {})
    stytch_org_id = org_data.get("organization_id")

    if not stytch_org_id:
        logger.warning("stytch_webhook_org_update_missing_id")
        return

    try:
        org = Organization.objects.get(stytch_org_id=stytch_org_id)
    except Organization.DoesNotExist:
        logger.info("stytch_webhook_org_not_found", stytch_org_id=stytch_org_id)
        return

    # Update fields that may have changed
    updated = False

    new_name = org_data.get("organization_name")
    if new_name and org.name != new_name:
        logger.info(
            "stytch_webhook_org_name_updated",
            stytch_org_id=stytch_org_id,
            old_name=org.name,
            new_name=new_name,
        )
        org.name = new_name
        updated = True

    new_slug = org_data.get("organization_slug")
    if new_slug and org.slug != new_slug:
        logger.info(
            "stytch_webhook_org_slug_updated",
            stytch_org_id=stytch_org_id,
            old_slug=org.slug,
            new_slug=new_slug,
        )
        org.slug = new_slug
        updated = True

    # Sync logo if changed
    new_logo = org_data.get("organization_logo_url", "")
    if org.logo_url != new_logo:
        org.logo_url = new_logo
        updated = True

    if updated:
        org.save()


def handle_organization_deleted(data: dict) -> None:
    """
    Handle organization.delete event from Stytch.

    Soft deletes the organization and all its members in local database.
    This handles deletion via Stytch dashboard or SCIM.
    """
    # Try both possible locations for org_id in the event payload
    stytch_org_id = data.get("id") or data.get("organization", {}).get("organization_id")

    if not stytch_org_id:
        logger.warning("stytch_webhook_org_delete_missing_id")
        return

    # Use all_objects to find even if already soft-deleted
    try:
        org = Organization.all_objects.get(stytch_org_id=stytch_org_id)
    except Organization.DoesNotExist:
        logger.debug("stytch_webhook_org_not_found", stytch_org_id=stytch_org_id)
        return

    if org.deleted_at is not None:
        logger.debug("stytch_webhook_org_already_deleted", stytch_org_id=stytch_org_id)
        return

    logger.info(
        "stytch_webhook_org_soft_deleting",
        stytch_org_id=stytch_org_id,
        org_name=org.name,
    )

    # Soft delete all members in the organization first
    members = Member.objects.filter(organization=org)
    member_count = members.count()
    for member in members:
        if member.deleted_at is None:
            member.soft_delete()

    if member_count > 0:
        logger.info(
            "stytch_webhook_members_soft_deleted",
            count=member_count,
            org_name=org.name,
        )

    # Soft delete the organization
    org.soft_delete()

    # Emit organization.deleted event
    publish_event(
        event_type="organization.deleted",
        aggregate=org,
        data={
            "name": org.name,
            "slug": org.slug,
            "member_count": member_count,
            "deleted_via": "stytch_webhook",
        },
        actor=None,  # System/webhook event
    )


@csrf_exempt
@require_POST
def stytch_webhook(request: HttpRequest) -> HttpResponse:
    """
    Handle Stytch webhook events.

    Verifies Svix signature and dispatches to appropriate handler.

    Stytch event types follow the pattern: source.object_type.action
    - source: 'direct', 'dashboard', 'scim'
    - object_type: 'member', 'organization', etc.
    - action: 'create', 'update', 'delete'
    """
    payload = request.body

    if not settings.STYTCH_WEBHOOK_SECRET:
        logger.error("stytch_webhook_secret_not_configured")
        return HttpResponse(status=500)

    # Verify Svix signature
    try:
        wh = Webhook(settings.STYTCH_WEBHOOK_SECRET)
        event = wh.verify(payload, dict(request.headers))
    except WebhookVerificationError as e:
        logger.warning("stytch_webhook_invalid_signature", error=str(e))
        return HttpResponse(status=400)
    except json.JSONDecodeError as e:
        logger.warning("stytch_webhook_invalid_json", error=str(e))
        return HttpResponse(status=400)

    # Get Svix message ID for idempotency
    event_id = request.headers.get("svix-id", "")
    if not event_id:
        logger.warning("stytch_webhook_missing_svix_id")
        return HttpResponse(status=400)

    # Parse event type: source.object_type.action
    event_type = event.get("event_type", "")
    action = event.get("action", "")
    object_type = event.get("object_type", "")

    logger.info(
        "stytch_webhook_received",
        event_id=event_id,
        event_type=event_type,
        action=action,
        object_type=object_type,
    )

    # Use transaction to ensure idempotency marker is rolled back if handler fails
    try:
        with transaction.atomic():
            # Idempotency check - skip if already processed
            if not mark_webhook_processed("stytch", event_id):
                logger.info("stytch_webhook_duplicate", event_id=event_id)
                return HttpResponse(status=200)

            # Dispatch to handlers based on object_type and action
            if object_type == "member":
                if action == "CREATE":
                    handle_member_created(event)
                elif action == "UPDATE":
                    handle_member_updated(event)
                elif action == "DELETE":
                    handle_member_deleted(event)
                else:
                    logger.debug("stytch_webhook_unhandled_member_action", action=action)

            elif object_type == "organization":
                if action == "UPDATE":
                    handle_organization_updated(event)
                elif action == "DELETE":
                    handle_organization_deleted(event)
                else:
                    logger.debug("stytch_webhook_unhandled_org_action", action=action)

            else:
                logger.debug("stytch_webhook_unhandled_object_type", object_type=object_type)

    except Exception:
        logger.exception("stytch_webhook_handler_error")
        # Return 500 so Svix will retry with exponential backoff
        # Transaction rollback ensures idempotency marker is not committed
        return HttpResponse(status=500)

    return HttpResponse(status=200)
