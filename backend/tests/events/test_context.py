"""
Tests for audit context manager.

Tests the audit_context context manager used for background jobs, Lambdas,
and management commands that publish events outside HTTP request context.
"""

from uuid import UUID

import pytest
import structlog

from apps.events.context import audit_context
from apps.events.services import get_correlation_id


class TestAuditContext:
    """Tests for audit_context context manager."""

    def test_binds_correlation_id_to_contextvars(self):
        """Should bind correlation_id to structlog contextvars."""
        test_correlation_id = "550e8400-e29b-41d4-a716-446655440000"

        with audit_context(correlation_id=test_correlation_id):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("correlation_id") == test_correlation_id

    def test_generates_correlation_id_if_not_provided(self):
        """Should generate a correlation_id if none provided."""
        with audit_context():
            ctx = structlog.contextvars.get_contextvars()
            correlation_id = ctx.get("correlation_id")
            assert correlation_id is not None
            # Should be a valid UUID string
            UUID(correlation_id)

    def test_binds_ip_address_to_contextvars(self):
        """Should bind ip_address to structlog contextvars."""
        with audit_context(ip_address="192.168.1.100"):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request.ip_address") == "192.168.1.100"

    def test_binds_user_agent_to_contextvars(self):
        """Should bind user_agent to structlog contextvars."""
        with audit_context(user_agent="TestAgent/1.0"):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request.user_agent") == "TestAgent/1.0"

    def test_sets_correlation_id_in_events_module(self):
        """Should set correlation_id in events services module."""
        test_correlation_id = "550e8400-e29b-41d4-a716-446655440001"

        with audit_context(correlation_id=test_correlation_id):
            correlation_id = get_correlation_id()
            assert correlation_id is not None
            assert str(correlation_id) == test_correlation_id

    def test_clears_context_after_exit(self):
        """Should clear all context after exiting the context manager."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440002"
        with audit_context(
            correlation_id=test_uuid,
            ip_address="192.168.1.1",
            user_agent="TestAgent",
        ):
            # Context should be set
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("correlation_id") == test_uuid

        # Context should be cleared
        ctx = structlog.contextvars.get_contextvars()
        assert "correlation_id" not in ctx
        assert "request.ip_address" not in ctx
        assert "request.user_agent" not in ctx

    def test_clears_correlation_id_after_exit(self):
        """Should clear correlation_id in events module after exit."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440003"
        with audit_context(correlation_id=test_uuid):
            assert get_correlation_id() is not None

        assert get_correlation_id() is None

    def test_clears_context_on_exception(self):
        """Should clear context even if an exception occurs."""
        test_uuid = "550e8400-e29b-41d4-a716-446655440004"
        with pytest.raises(RuntimeError), audit_context(correlation_id=test_uuid):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("correlation_id") == test_uuid
            raise RuntimeError("Test exception")

        # Context should still be cleared
        ctx = structlog.contextvars.get_contextvars()
        assert "correlation_id" not in ctx

    def test_handles_none_ip_address(self):
        """Should handle None ip_address gracefully."""
        with audit_context(ip_address=None):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request.ip_address") is None

    def test_defaults_user_agent_to_empty_string(self):
        """Should default user_agent to empty string."""
        with audit_context():
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request.user_agent") == ""
