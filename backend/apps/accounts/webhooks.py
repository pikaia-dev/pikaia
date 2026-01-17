"""
Stytch webhook handler.

Handles incoming webhooks from Stytch for member and organization events.
Stytch uses Svix for webhook delivery and signature verification.
"""

import json
from datetime import UTC, datetime

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from svix.webhooks import Webhook, WebhookVerificationError

from apps.accounts.models import Member
from apps.core.logging import get_logger
from apps.events.services import publish_event
from apps.organizations.models import Organization
from config.settings.base import settings

logger = get_logger(__name__)


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
        member = Member.objects.get(stytch_member_id=stytch_member_id)
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
        member = Member.objects.get(stytch_member_id=member_id)
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
        logger.info("stytch_webhook_org_name_updated", stytch_org_id=stytch_org_id, old_name=org.name, new_name=new_name)
        org.name = new_name
        updated = True

    new_slug = org_data.get("organization_slug")
    if new_slug and org.slug != new_slug:
        logger.info("stytch_webhook_org_slug_updated", stytch_org_id=stytch_org_id, old_slug=org.slug, new_slug=new_slug)
        org.slug = new_slug
        updated = True

    # Sync logo if changed
    new_logo = org_data.get("organization_logo_url", "")
    if org.logo_url != new_logo:
        org.logo_url = new_logo
        updated = True

    if updated:
        org.save()


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
        event = wh.verify(payload, request.headers)
    except WebhookVerificationError as e:
        logger.warning("stytch_webhook_invalid_signature", error=str(e))
        return HttpResponse(status=400)
    except json.JSONDecodeError as e:
        logger.warning("stytch_webhook_invalid_json", error=str(e))
        return HttpResponse(status=400)

    # Parse event type: source.object_type.action
    event_type = event.get("event_type", "")
    action = event.get("action", "")
    object_type = event.get("object_type", "")

    logger.info(
        "stytch_webhook_received", event_type=event_type, action=action, object_type=object_type
    )

    # Dispatch to handlers based on object_type and action
    try:
        if object_type == "member":
            if action == "UPDATE":
                handle_member_updated(event)
            elif action == "DELETE":
                handle_member_deleted(event)
            else:
                logger.debug("stytch_webhook_unhandled_member_action", action=action)

        elif object_type == "organization":
            if action == "UPDATE":
                handle_organization_updated(event)
            else:
                logger.debug("stytch_webhook_unhandled_org_action", action=action)

        else:
            logger.debug("stytch_webhook_unhandled_object_type", object_type=object_type)

    except Exception:
        logger.exception("stytch_webhook_handler_error")
        # Return 500 so Svix will retry with exponential backoff
        return HttpResponse(status=500)

    return HttpResponse(status=200)
