"""
REST Hooks API - Subscription endpoints for Zapier/Make integration.

This module implements the REST Hooks pattern (https://resthooks.org/),
allowing external services like Zapier and Make to programmatically
subscribe to webhook events.

Endpoints:
    POST /api/v1/hooks          - Subscribe to events
    GET /api/v1/hooks           - List subscriptions
    DELETE /api/v1/hooks/{id}   - Unsubscribe
    GET /api/v1/hooks/samples/{event_type} - Get sample payload
    GET /api/v1/hooks/auth/test - Test authentication
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.core.schemas import ErrorResponse
from apps.core.security import BearerAuth, require_admin

from .events import WEBHOOK_EVENTS, get_event_type
from .models import WebhookEndpoint
from .schemas import (
    AuthTestResponse,
    EventSampleResponse,
    RestHookListResponse,
    RestHookSubscribeRequest,
    RestHookSubscribeResponse,
    WebhookPayload,
)
from .services import WebhookService


@dataclass
class RestHookEndpointData:
    """Data for creating a REST Hook endpoint."""

    name: str
    description: str
    url: str
    events: list[str]

logger = logging.getLogger(__name__)

router = Router(tags=["hooks"])
bearer_auth = BearerAuth()


def _detect_source(target_url: str) -> str:
    """Detect the source based on the target URL domain."""
    parsed = urlparse(target_url)
    domain = parsed.netloc.lower()

    if "zapier.com" in domain:
        return WebhookEndpoint.Source.ZAPIER
    elif "make.com" in domain or "integromat.com" in domain:
        return WebhookEndpoint.Source.MAKE
    else:
        return WebhookEndpoint.Source.REST_HOOKS


# =============================================================================
# Subscribe / Unsubscribe
# =============================================================================


@router.post(
    "",
    response={201: RestHookSubscribeResponse, 400: ErrorResponse},
    auth=bearer_auth,
    operation_id="subscribeHook",
    summary="Subscribe to webhook events",
)
@require_admin
def subscribe(
    request: HttpRequest,
    payload: RestHookSubscribeRequest,
) -> tuple[int, RestHookSubscribeResponse]:
    """
    Create a new webhook subscription (REST Hooks pattern).

    This endpoint is designed for Zapier/Make to call when a user
    creates a trigger. The subscription ID is returned and should
    be stored for unsubscribe.

    Returns:
        201: Subscription created with ID for unsubscribe
        400: Invalid event type or URL
    """
    service = WebhookService(request.auth_organization)
    source = _detect_source(payload.target_url)

    # Create endpoint with auto-generated name based on source
    event_def = get_event_type(payload.event_type)
    name = f"{source.label} - {event_def.description if event_def else payload.event_type}"

    endpoint_data = RestHookEndpointData(
        name=name[:100],  # Truncate to max length
        description=f"Auto-created by {source.label}",
        url=payload.target_url,
        events=[payload.event_type],
    )

    endpoint = service.create_endpoint(
        data=endpoint_data,
        created_by_id=request.auth_member.user_id if request.auth_member else None,
        source=source,
    )

    logger.info(
        "REST Hook subscription created: %s for %s (%s)",
        endpoint.id,
        payload.event_type,
        source,
    )

    return 201, RestHookSubscribeResponse(
        id=endpoint.id,
        target_url=endpoint.url,
        event_type=payload.event_type,
        status="active",
        created_at=endpoint.created_at,
    )


@router.get(
    "",
    response={200: RestHookListResponse},
    auth=bearer_auth,
    operation_id="listHooks",
    summary="List webhook subscriptions",
)
@require_admin
def list_subscriptions(request: HttpRequest) -> RestHookListResponse:
    """
    List all REST Hook subscriptions for the organization.

    Returns subscriptions created via REST Hooks (Zapier, Make, etc.),
    not manually created webhook endpoints.
    """
    service = WebhookService(request.auth_organization)
    endpoints = service.list_endpoints()

    subscriptions = [
        RestHookSubscribeResponse(
            id=ep.id,
            target_url=ep.url,
            event_type=ep.events[0] if ep.events else "",
            status="active" if ep.active else "inactive",
            created_at=ep.created_at,
        )
        for ep in endpoints
        if ep.source in WebhookEndpoint.REST_HOOK_SOURCES
    ]

    return RestHookListResponse(subscriptions=subscriptions)


@router.delete(
    "/{subscription_id}",
    response={204: None, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="unsubscribeHook",
    summary="Unsubscribe from webhook events",
)
@require_admin
def unsubscribe(
    request: HttpRequest,
    subscription_id: str,
) -> tuple[int, None]:
    """
    Delete a webhook subscription (REST Hooks pattern).

    This endpoint is called by Zapier/Make when a user deletes
    their trigger or disables the Zap/scenario.

    Returns:
        204: Subscription deleted
        404: Subscription not found
    """
    service = WebhookService(request.auth_organization)
    deleted = service.delete_endpoint(subscription_id)

    if not deleted:
        raise HttpError(404, "Subscription not found")

    logger.info(
        "REST Hook subscription deleted: %s",
        subscription_id,
    )

    return 204, None


# =============================================================================
# Sample Payloads (for Zapier's performList)
# =============================================================================


@router.get(
    "/samples/{event_type}",
    response={200: EventSampleResponse, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="getEventSample",
    summary="Get sample payload for event type",
)
@require_admin
def get_sample(
    request: HttpRequest,
    event_type: str,
) -> EventSampleResponse:
    """
    Get a sample payload for a specific event type.

    This is used by Zapier's performList function to populate
    the trigger form with sample data.

    Returns:
        200: Sample payload
        404: Unknown event type
    """
    event = WEBHOOK_EVENTS.get(event_type)
    if not event:
        raise HttpError(404, f"Unknown event type: {event_type}")

    # Build a full sample payload using the same schema as actual deliveries
    sample = WebhookPayload(
        id="evt_sample123",
        spec_version="1.0",
        type=event.type,
        timestamp=datetime.now(UTC),
        organization_id=str(request.auth_organization.id),
        data=event.payload_example,
    )

    return EventSampleResponse(
        event_type=event.type,
        description=event.description,
        sample_payload=sample.model_dump(),
    )


# =============================================================================
# Auth Test
# =============================================================================


@router.get(
    "/auth/test",
    response={200: AuthTestResponse},
    auth=bearer_auth,
    operation_id="testAuth",
    summary="Test authentication",
)
@require_admin
def verify_auth(request: HttpRequest) -> AuthTestResponse:
    """
    Test that authentication is working.

    This endpoint is required by Zapier to verify that the
    user's API credentials are valid.

    Returns:
        200: Authentication successful with organization info
    """
    return AuthTestResponse(
        ok=True,
        organization_id=str(request.auth_organization.id),
        organization_name=request.auth_organization.name,
    )
