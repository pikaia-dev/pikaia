"""
Webhook service layer - business logic for webhook management and delivery.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from apps.organizations.models import Organization

from .events import WEBHOOK_EVENTS, get_event_type, matches_subscription
from .models import WebhookDelivery, WebhookEndpoint
from .schemas import WebhookEndpointCreate, WebhookEndpointUpdate, WebhookPayload
from .signing import generate_headers

logger = logging.getLogger(__name__)

# Delivery timeout in seconds
DELIVERY_TIMEOUT = 30


@dataclass
class DeliveryResult:
    """Result of a webhook delivery attempt."""

    success: bool
    http_status: int | None
    duration_ms: int
    response_snippet: str
    error_type: str = ""
    error_message: str = ""
    signature: str = ""


class WebhookService:
    """Service for managing webhook endpoints."""

    def __init__(self, organization: Organization):
        self.organization = organization

    def list_endpoints(self) -> list[WebhookEndpoint]:
        """List all webhook endpoints for the organization."""
        return list(
            WebhookEndpoint.objects.filter(organization=self.organization).order_by("-created_at")
        )

    def get_endpoint(self, endpoint_id: str) -> WebhookEndpoint | None:
        """Get a specific webhook endpoint."""
        return WebhookEndpoint.objects.filter(
            id=endpoint_id,
            organization=self.organization,
        ).first()

    def create_endpoint(
        self,
        data: WebhookEndpointCreate,
        created_by_id: int | None = None,
    ) -> WebhookEndpoint:
        """Create a new webhook endpoint."""
        return WebhookEndpoint.objects.create(
            organization=self.organization,
            created_by_id=created_by_id,
            name=data.name,
            description=data.description,
            url=data.url,
            events=data.events,
        )

    def update_endpoint(
        self,
        endpoint_id: str,
        data: WebhookEndpointUpdate,
    ) -> WebhookEndpoint | None:
        """Update a webhook endpoint."""
        endpoint = self.get_endpoint(endpoint_id)
        if not endpoint:
            return None

        # Update only provided fields
        if data.name is not None:
            endpoint.name = data.name
        if data.description is not None:
            endpoint.description = data.description
        if data.url is not None:
            endpoint.url = data.url
        if data.events is not None:
            endpoint.events = data.events
        if data.active is not None:
            endpoint.active = data.active

        endpoint.save()
        return endpoint

    def delete_endpoint(self, endpoint_id: str) -> bool:
        """Delete a webhook endpoint."""
        endpoint = self.get_endpoint(endpoint_id)
        if not endpoint:
            return False
        endpoint.delete()
        return True

    def list_deliveries(
        self,
        endpoint_id: str,
        limit: int = 50,
    ) -> list[WebhookDelivery]:
        """List delivery logs for an endpoint."""
        return list(
            WebhookDelivery.objects.filter(
                endpoint_id=endpoint_id,
                endpoint__organization=self.organization,
            )
            .order_by("-created_at")
            .select_related("endpoint")[:limit]
        )


class WebhookDispatcher:
    """Service for dispatching webhook requests."""

    def __init__(self, timeout: int = DELIVERY_TIMEOUT):
        self.timeout = timeout

    def dispatch(
        self,
        endpoint: WebhookEndpoint,
        event_id: str,
        event_type: str,
        event_data: dict,
        organization_id: str,
        timestamp: datetime | None = None,
    ) -> DeliveryResult:
        """
        Dispatch a webhook to an endpoint.

        Args:
            endpoint: The webhook endpoint to send to
            event_id: Unique event identifier
            event_type: Type of event (e.g., "member.created")
            event_data: Event-specific payload data
            organization_id: Organization ID
            timestamp: Event timestamp (defaults to now)

        Returns:
            DeliveryResult with success status and details
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        # Build payload
        payload = WebhookPayload(
            id=event_id,
            spec_version="1.0",
            type=event_type,
            timestamp=timestamp,
            organization_id=organization_id,
            data=event_data,
        )
        payload_json = payload.model_dump_json()

        # Generate signed headers
        headers = generate_headers(payload_json, endpoint.secret, event_id)

        # Send request
        start_time = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    endpoint.url,
                    content=payload_json,
                    headers=headers,
                )

            duration_ms = int((time.monotonic() - start_time) * 1000)
            response_snippet = response.text[:500] if response.text else ""

            if 200 <= response.status_code < 300:
                return DeliveryResult(
                    success=True,
                    http_status=response.status_code,
                    duration_ms=duration_ms,
                    response_snippet=response_snippet,
                    signature=headers["X-Webhook-Signature"],
                )
            else:
                return DeliveryResult(
                    success=False,
                    http_status=response.status_code,
                    duration_ms=duration_ms,
                    response_snippet=response_snippet,
                    error_type=WebhookDelivery.ErrorType.HTTP_ERROR,
                    error_message=f"HTTP {response.status_code}",
                    signature=headers["X-Webhook-Signature"],
                )

        except httpx.TimeoutException:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return DeliveryResult(
                success=False,
                http_status=None,
                duration_ms=duration_ms,
                response_snippet="",
                error_type=WebhookDelivery.ErrorType.TIMEOUT,
                error_message=f"Request timed out after {self.timeout}s",
                signature=headers["X-Webhook-Signature"],
            )

        except httpx.ConnectError as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return DeliveryResult(
                success=False,
                http_status=None,
                duration_ms=duration_ms,
                response_snippet="",
                error_type=WebhookDelivery.ErrorType.CONNECTION_ERROR,
                error_message=str(e),
                signature=headers["X-Webhook-Signature"],
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.exception("Unexpected error dispatching webhook to %s", endpoint.url)
            return DeliveryResult(
                success=False,
                http_status=None,
                duration_ms=duration_ms,
                response_snippet="",
                error_type=WebhookDelivery.ErrorType.CONNECTION_ERROR,
                error_message=str(e),
                signature=headers.get("X-Webhook-Signature", ""),
            )

    def send_test(
        self,
        endpoint: WebhookEndpoint,
        event_type: str,
    ) -> DeliveryResult:
        """
        Send a test webhook with sample data.

        Args:
            endpoint: The webhook endpoint to test
            event_type: The event type to simulate

        Returns:
            DeliveryResult with test results
        """
        event_def = get_event_type(event_type)
        if not event_def:
            return DeliveryResult(
                success=False,
                http_status=None,
                duration_ms=0,
                response_snippet="",
                error_type="invalid_event",
                error_message=f"Unknown event type: {event_type}",
            )

        # Generate test event ID
        test_event_id = f"evt_test_{uuid.uuid4().hex[:16]}"

        return self.dispatch(
            endpoint=endpoint,
            event_id=test_event_id,
            event_type=event_type,
            event_data=event_def.payload_example,
            organization_id=str(endpoint.organization_id),
        )


def get_subscribed_endpoints(
    organization_id: str,
    event_type: str,
) -> list[WebhookEndpoint]:
    """
    Get all active endpoints subscribed to an event type.

    Args:
        organization_id: The organization to filter by
        event_type: The event type to match

    Returns:
        List of matching endpoints
    """
    endpoints = WebhookEndpoint.objects.filter(
        organization_id=organization_id,
        active=True,
    )

    # Filter by event subscription (supports wildcards)
    return [ep for ep in endpoints if matches_subscription(event_type, ep.events)]


def dispatch_event_to_subscribers(
    organization_id: str,
    event_id: str,
    event_type: str,
    event_data: dict,
    timestamp: datetime | None = None,
) -> list[tuple[WebhookEndpoint, DeliveryResult]]:
    """
    Dispatch an event to all subscribed endpoints.

    Creates delivery records and handles retries.

    Args:
        organization_id: Organization this event belongs to
        event_id: Unique event identifier
        event_type: Type of event
        event_data: Event payload data
        timestamp: Event timestamp

    Returns:
        List of (endpoint, result) tuples
    """
    endpoints = get_subscribed_endpoints(organization_id, event_type)
    results: list[tuple[WebhookEndpoint, DeliveryResult]] = []
    dispatcher = WebhookDispatcher()

    for endpoint in endpoints:
        # Create or get existing delivery record (idempotent)
        delivery = WebhookDelivery.create_for_event(
            endpoint=endpoint,
            event_id=event_id,
            event_type=event_type,
        )

        # Skip if already successfully delivered
        if delivery.status == WebhookDelivery.Status.SUCCESS:
            logger.info(
                "Skipping already delivered event %s to %s",
                event_id,
                endpoint.name,
            )
            continue

        # Dispatch
        result = dispatcher.dispatch(
            endpoint=endpoint,
            event_id=event_id,
            event_type=event_type,
            event_data=event_data,
            organization_id=organization_id,
            timestamp=timestamp,
        )

        # Update delivery record
        if result.success:
            delivery.mark_success(
                http_status=result.http_status or 200,
                duration_ms=result.duration_ms,
                response_snippet=result.response_snippet,
            )
        else:
            delivery.mark_failure(
                error_type=result.error_type,
                error_message=result.error_message,
                http_status=result.http_status,
                duration_ms=result.duration_ms,
                response_snippet=result.response_snippet,
                terminal=(result.http_status in (410, 404)),
            )

        results.append((endpoint, result))

    return results


def get_available_events() -> list[dict]:
    """Get all available webhook events for the event catalog."""
    return [
        {
            "type": event.type,
            "description": event.description,
            "category": event.category,
            "payload_example": event.payload_example,
        }
        for event in WEBHOOK_EVENTS.values()
    ]
