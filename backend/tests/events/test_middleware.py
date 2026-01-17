"""
Tests for CorrelationIdMiddleware.
"""

from uuid import UUID

from django.test import RequestFactory

from apps.core.middleware import CorrelationIdMiddleware
from apps.events.services import get_correlation_id


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware."""

    def test_generates_correlation_id_when_missing(self):
        """Test middleware generates UUID when header missing."""
        factory = RequestFactory()
        request = factory.get("/api/v1/health")

        # Track the correlation_id set during request
        captured_id = None

        def get_response(req):
            nonlocal captured_id
            captured_id = req.correlation_id
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(get_response)
        response = middleware(request)

        # Verify correlation ID was set and is a valid UUID
        assert captured_id is not None
        assert isinstance(captured_id, UUID)

        # Verify response header
        assert response["X-Correlation-ID"] == str(captured_id)

    def test_uses_existing_correlation_id_from_header(self):
        """Test middleware uses existing header value."""
        factory = RequestFactory()
        existing_id = "550e8400-e29b-41d4-a716-446655440000"
        request = factory.get("/api/v1/health", HTTP_X_CORRELATION_ID=existing_id)

        captured_id = None

        def get_response(req):
            nonlocal captured_id
            captured_id = req.correlation_id
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(get_response)
        response = middleware(request)

        assert str(captured_id) == existing_id
        assert response["X-Correlation-ID"] == existing_id

    def test_generates_new_id_for_invalid_header(self):
        """Test middleware generates new ID if header is invalid UUID."""
        factory = RequestFactory()
        request = factory.get("/api/v1/health", HTTP_X_CORRELATION_ID="not-a-uuid")

        captured_id = None

        def get_response(req):
            nonlocal captured_id
            captured_id = req.correlation_id
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(get_response)
        middleware(request)

        # Should generate new valid UUID
        assert captured_id is not None
        assert isinstance(captured_id, UUID)
        assert str(captured_id) != "not-a-uuid"

    def test_clears_correlation_id_after_request(self):
        """Test correlation ID is cleared from context after request."""
        factory = RequestFactory()
        request = factory.get("/api/v1/health")

        def get_response(req):
            # Verify it's set during request
            assert get_correlation_id() is not None
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(get_response)
        middleware(request)

        # Should be cleared after request completes
        assert get_correlation_id() is None

    def test_correlation_id_available_in_event_services(self):
        """Test correlation ID is accessible from event services during request."""
        factory = RequestFactory()
        request = factory.get("/api/v1/health")

        service_correlation_id = None

        def get_response(req):
            nonlocal service_correlation_id
            service_correlation_id = get_correlation_id()
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = CorrelationIdMiddleware(get_response)
        middleware(request)

        assert service_correlation_id is not None
        assert isinstance(service_correlation_id, UUID)
