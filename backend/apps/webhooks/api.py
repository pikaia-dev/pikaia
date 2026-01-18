"""
Webhook API endpoints.

Allows organization admins to manage webhook endpoints and view delivery logs.
"""

import logging

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.core.schemas import ErrorResponse
from apps.core.security import BearerAuth, require_admin

from .schemas import (
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointListResponse,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
    WebhookEndpointWithSecretResponse,
    WebhookEventListResponse,
    WebhookEventTypeResponse,
    WebhookTestRequest,
    WebhookTestResponse,
)
from .services import WebhookDispatcher, WebhookService, get_available_events

logger = logging.getLogger(__name__)

router = Router(tags=["webhooks"])
bearer_auth = BearerAuth()


# =============================================================================
# Helpers
# =============================================================================


def _endpoint_to_response(endpoint) -> WebhookEndpointResponse:
    """Convert a WebhookEndpoint model to response schema."""
    return WebhookEndpointResponse(
        id=endpoint.id,
        name=endpoint.name,
        description=endpoint.description,
        url=endpoint.url,
        events=endpoint.events,
        active=endpoint.active,
        last_delivery_status=endpoint.last_delivery_status,
        last_delivery_at=endpoint.last_delivery_at,
        consecutive_failures=endpoint.consecutive_failures,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


def _delivery_to_response(delivery) -> WebhookDeliveryResponse:
    """Convert a WebhookDelivery model to response schema."""
    return WebhookDeliveryResponse(
        id=delivery.id,
        event_id=delivery.event_id,
        event_type=delivery.event_type,
        status=delivery.status,
        error_type=delivery.error_type,
        http_status=delivery.http_status,
        duration_ms=delivery.duration_ms,
        response_snippet=delivery.response_snippet,
        attempt_number=delivery.attempt_number,
        attempted_at=delivery.attempted_at,
        created_at=delivery.created_at,
    )


# =============================================================================
# Event Catalog (public within auth)
# =============================================================================


@router.get(
    "/events",
    response={200: WebhookEventListResponse},
    auth=bearer_auth,
    operation_id="listWebhookEvents",
    summary="List available webhook events",
)
def list_events(request: HttpRequest) -> WebhookEventListResponse:
    """
    Get the catalog of all available webhook event types.

    Returns event types with descriptions and example payloads.
    This endpoint is the single source of truth for what events can be subscribed to.
    """
    events = get_available_events()
    return WebhookEventListResponse(events=[WebhookEventTypeResponse(**e) for e in events])


# =============================================================================
# Endpoint Management (admin only)
# =============================================================================


@router.get(
    "/endpoints",
    response={200: WebhookEndpointListResponse},
    auth=bearer_auth,
    operation_id="listWebhookEndpoints",
    summary="List webhook endpoints",
)
@require_admin
def list_endpoints(request: HttpRequest) -> WebhookEndpointListResponse:
    """
    List all webhook endpoints for the organization.

    Requires admin role.
    """
    service = WebhookService(request.auth_organization)
    endpoints = service.list_endpoints()

    return WebhookEndpointListResponse(endpoints=[_endpoint_to_response(ep) for ep in endpoints])


@router.post(
    "/endpoints",
    response={201: WebhookEndpointWithSecretResponse, 400: ErrorResponse},
    auth=bearer_auth,
    operation_id="createWebhookEndpoint",
    summary="Create webhook endpoint",
)
@require_admin
def create_endpoint(
    request: HttpRequest,
    payload: WebhookEndpointCreate,
) -> tuple[int, WebhookEndpointWithSecretResponse]:
    """
    Create a new webhook endpoint.

    Returns the endpoint including the signing secret.
    **Important:** The secret is only returned on creation. Store it securely.

    Requires admin role.
    """
    service = WebhookService(request.auth_organization)
    endpoint = service.create_endpoint(
        data=payload,
        created_by_id=request.auth_member.user_id if request.auth_member else None,
    )

    logger.info(
        "Created webhook endpoint %s for org %s",
        endpoint.id,
        request.auth_organization.id,
    )

    return 201, WebhookEndpointWithSecretResponse(
        id=endpoint.id,
        name=endpoint.name,
        description=endpoint.description,
        url=endpoint.url,
        events=endpoint.events,
        active=endpoint.active,
        secret=endpoint.secret,
        last_delivery_status=endpoint.last_delivery_status,
        last_delivery_at=endpoint.last_delivery_at,
        consecutive_failures=endpoint.consecutive_failures,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


@router.get(
    "/endpoints/{endpoint_id}",
    response={200: WebhookEndpointResponse, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="getWebhookEndpoint",
    summary="Get webhook endpoint",
)
@require_admin
def get_endpoint(request: HttpRequest, endpoint_id: str) -> WebhookEndpointResponse:
    """
    Get a specific webhook endpoint.

    Requires admin role.
    """
    service = WebhookService(request.auth_organization)
    endpoint = service.get_endpoint(endpoint_id)

    if not endpoint:
        raise HttpError(404, "Webhook endpoint not found")

    return _endpoint_to_response(endpoint)


@router.patch(
    "/endpoints/{endpoint_id}",
    response={200: WebhookEndpointResponse, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="updateWebhookEndpoint",
    summary="Update webhook endpoint",
)
@require_admin
def update_endpoint(
    request: HttpRequest,
    endpoint_id: str,
    payload: WebhookEndpointUpdate,
) -> WebhookEndpointResponse:
    """
    Update a webhook endpoint.

    Partial updates are supported - only provided fields are updated.

    Requires admin role.
    """
    service = WebhookService(request.auth_organization)
    endpoint = service.update_endpoint(endpoint_id, payload)

    if not endpoint:
        raise HttpError(404, "Webhook endpoint not found")

    logger.info(
        "Updated webhook endpoint %s for org %s",
        endpoint_id,
        request.auth_organization.id,
    )

    return _endpoint_to_response(endpoint)


@router.delete(
    "/endpoints/{endpoint_id}",
    response={204: None, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="deleteWebhookEndpoint",
    summary="Delete webhook endpoint",
)
@require_admin
def delete_endpoint(request: HttpRequest, endpoint_id: str) -> tuple[int, None]:
    """
    Delete a webhook endpoint.

    All associated delivery logs will also be deleted.

    Requires admin role.
    """
    service = WebhookService(request.auth_organization)
    deleted = service.delete_endpoint(endpoint_id)

    if not deleted:
        raise HttpError(404, "Webhook endpoint not found")

    logger.info(
        "Deleted webhook endpoint %s for org %s",
        endpoint_id,
        request.auth_organization.id,
    )

    return 204, None


# =============================================================================
# Delivery Logs
# =============================================================================


@router.get(
    "/endpoints/{endpoint_id}/deliveries",
    response={200: WebhookDeliveryListResponse, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="listWebhookDeliveries",
    summary="List webhook deliveries",
)
@require_admin
def list_deliveries(
    request: HttpRequest,
    endpoint_id: str,
    limit: int = 50,
) -> WebhookDeliveryListResponse:
    """
    List delivery logs for a webhook endpoint.

    Returns the most recent deliveries first.

    Requires admin role.
    """
    service = WebhookService(request.auth_organization)

    # Verify endpoint exists and belongs to org
    endpoint = service.get_endpoint(endpoint_id)
    if not endpoint:
        raise HttpError(404, "Webhook endpoint not found")

    deliveries = service.list_deliveries(endpoint_id, limit=min(limit, 100))

    return WebhookDeliveryListResponse(deliveries=[_delivery_to_response(d) for d in deliveries])


# =============================================================================
# Test Webhook
# =============================================================================


@router.post(
    "/endpoints/{endpoint_id}/test",
    response={200: WebhookTestResponse, 404: ErrorResponse},
    auth=bearer_auth,
    operation_id="testWebhookEndpoint",
    summary="Send test webhook",
)
@require_admin
def send_test_webhook(
    request: HttpRequest,
    endpoint_id: str,
    payload: WebhookTestRequest,
) -> WebhookTestResponse:
    """
    Send a test webhook to verify the endpoint is working.

    Sends a sample event with example payload data.
    Returns the delivery result including the signature for verification.

    Requires admin role.
    """
    service = WebhookService(request.auth_organization)
    endpoint = service.get_endpoint(endpoint_id)

    if not endpoint:
        raise HttpError(404, "Webhook endpoint not found")

    dispatcher = WebhookDispatcher()
    result = dispatcher.send_test(endpoint, payload.event_type)

    logger.info(
        "Test webhook sent to %s (success=%s, status=%s)",
        endpoint.url,
        result.success,
        result.http_status,
    )

    return WebhookTestResponse(
        success=result.success,
        http_status=result.http_status,
        duration_ms=result.duration_ms,
        signature=result.signature,
        response_snippet=result.response_snippet,
        error_message=result.error_message,
    )
