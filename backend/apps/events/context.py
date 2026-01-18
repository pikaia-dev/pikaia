"""
Audit context for non-request code paths.

Provides a context manager to bind request-like context for background jobs,
Lambda functions, Celery tasks, and management commands that publish events
outside HTTP request context.
"""

from collections.abc import Generator
from contextlib import contextmanager
from uuid import uuid4

import structlog

from apps.events.services import set_correlation_id


@contextmanager
def audit_context(
    correlation_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> Generator[None, None, None]:
    """
    Bind audit context for non-request code (background jobs, Lambdas, etc.).

    This context manager ensures that events published from background code
    have the same structured context as HTTP requests.

    Usage:
        with audit_context(correlation_id=str(uuid4())):
            publish_event(...)  # Context is available

        # Context automatically cleaned up after block

    For Lambda event replay, pass the original correlation_id:
        with audit_context(correlation_id=event["correlation_id"]):
            process_event(event)

    Args:
        correlation_id: Request trace ID. Auto-generated if not provided.
        ip_address: Original client IP (for audit trail).
        user_agent: Original client user-agent (for audit trail).
    """
    generated_correlation_id = correlation_id or str(uuid4())

    ctx = {
        "correlation_id": generated_correlation_id,
        "request.ip_address": ip_address,
        "request.user_agent": user_agent,
    }

    # Set correlation ID in events module
    from uuid import UUID

    set_correlation_id(UUID(generated_correlation_id))

    # Bind contextvars for structlog
    structlog.contextvars.bind_contextvars(**ctx)
    try:
        yield
    finally:
        # Clean up
        set_correlation_id(None)
        structlog.contextvars.unbind_contextvars(*ctx.keys())
