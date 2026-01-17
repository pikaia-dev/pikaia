"""
Structured logging configuration using structlog.

This module configures structured logging with Datadog-compatible field names
for easy integration with observability platforms (Datadog, Elastic, CloudWatch).

Usage:
    from apps.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("user_created", usr_id="123", email="user@example.com")

Field naming follows Datadog standard attributes:
    - trace_id: Request correlation ID for distributed tracing
    - usr.id: User identifier
    - usr.email: User email
    - organization.id: Organization/tenant identifier
    - http.method: HTTP request method
    - http.url_details.path: Request path
    - http.status_code: Response status code
    - duration: Request duration in nanoseconds (Datadog standard)

See: https://docs.datadoghq.com/logs/log_configuration/attributes_naming_convention/
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def _add_datadog_trace_fields(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Rename correlation_id to trace_id for Datadog APM compatibility.

    Also ensures the trace_id field is a string.
    """
    if "correlation_id" in event_dict:
        event_dict["trace_id"] = str(event_dict.pop("correlation_id"))
    return event_dict


def _convert_duration_to_nanoseconds(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Convert duration_ms to duration (nanoseconds) for Datadog compatibility.

    Datadog expects duration in nanoseconds for proper latency analysis.
    """
    if "duration_ms" in event_dict:
        duration_ms = event_dict.pop("duration_ms")
        event_dict["duration"] = int(duration_ms * 1_000_000)  # ms to ns
    return event_dict


def _rename_level_for_datadog(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Ensure level field uses standard naming.

    structlog uses 'level', which is already Datadog-compatible.
    """
    return event_dict


def configure_logging(json_format: bool = True, log_level: str = "INFO") -> None:
    """
    Configure structlog for the application.

    Args:
        json_format: If True, output JSON (production). If False, pretty console output (development).
        log_level: Minimum log level to output.
    """
    # Shared processors for all configurations
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_datadog_trace_fields,
        _convert_duration_to_nanoseconds,
    ]

    if json_format:
        # Production: JSON output with exception formatting
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console output with colors
        processors = [
            *shared_processors,
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    # This ensures third-party libraries (Django, etc.) also output structured logs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A bound structlog logger with context support.

    Usage:
        logger = get_logger(__name__)
        logger.info("event_name", key="value", another_key=123)
    """
    return structlog.get_logger(name)


def bind_contextvars(**kwargs: Any) -> None:
    """
    Bind key-value pairs to the current context.

    These values will be included in all subsequent log messages
    within the current request/task context.

    Args:
        **kwargs: Key-value pairs to bind to context.

    Usage:
        bind_contextvars(
            trace_id=str(correlation_id),
            **{"usr.id": str(user.id)},  # Use dict unpacking for dotted keys
        )
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_contextvars() -> None:
    """
    Clear all bound context variables.

    Call this at the end of request processing to prevent
    context leakage between requests (especially in async workers).
    """
    structlog.contextvars.clear_contextvars()
