"""
Webhook utilities for idempotent processing.
"""

from django.db import IntegrityError

from apps.core.logging import get_logger
from apps.core.models import ProcessedWebhook

logger = get_logger(__name__)


def is_webhook_processed(source: str, event_id: str) -> bool:
    """
    Check if a webhook event has already been processed.

    Args:
        source: Webhook provider (e.g., 'stripe', 'stytch')
        event_id: Unique event identifier from the provider

    Returns:
        True if already processed, False otherwise
    """
    return ProcessedWebhook.objects.filter(source=source, event_id=event_id).exists()


def mark_webhook_processed(source: str, event_id: str) -> bool:
    """
    Mark a webhook event as processed.

    Uses INSERT with unique constraint to handle race conditions.

    Args:
        source: Webhook provider (e.g., 'stripe', 'stytch')
        event_id: Unique event identifier from the provider

    Returns:
        True if marked successfully, False if already processed
    """
    try:
        ProcessedWebhook.objects.create(source=source, event_id=event_id)
        return True
    except IntegrityError:
        logger.debug(
            "webhook_already_processed",
            source=source,
            event_id=event_id,
        )
        return False
