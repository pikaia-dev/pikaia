"""
Reusable rate limiting utilities for API endpoints.

Uses Django's cache framework (database cache) for distributed rate limiting
across multiple ECS tasks. Follows the same patterns as existing rate limiting
in apps/devices and apps/sms.

Usage::

    from apps.core.throttling import check_rate_limit, RateLimitExceeded

    # In a view function:
    try:
        check_rate_limit(f"magic_link_send:{email}", max_requests=5, window_seconds=900)
    except RateLimitExceeded as e:
        raise HttpError(429, str(e))
"""

from django.core.cache import cache

from apps.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def check_rate_limit(
    key: str,
    *,
    max_requests: int,
    window_seconds: int,
) -> None:
    """
    Check and increment a rate limit counter.

    Uses ``cache.add()`` + ``cache.incr()`` for near-atomic increments.
    ``add()`` is a no-op when the key exists, and ``incr()`` uses
    ``SELECT ... FOR UPDATE`` in Django's DatabaseCache, preventing most
    race conditions across concurrent ECS tasks.

    Args:
        key: Cache key identifying the rate limit bucket
            (e.g., "magic_link_send:user@example.com").
        max_requests: Maximum allowed requests within the window.
        window_seconds: Time window in seconds.

    Raises:
        RateLimitExceeded: If the limit has been reached.
    """
    cache_key = f"rate_limit:{key}"

    # Atomically create key with 0 if it doesn't exist (no-op if it does)
    cache.add(cache_key, 0, timeout=window_seconds)

    # Atomically increment and get new value
    try:
        current = cache.incr(cache_key)
    except ValueError:
        # Key expired between add() and incr() — treat as first request
        cache.set(cache_key, 1, timeout=window_seconds)
        return

    if current > max_requests:
        logger.warning("rate_limit_exceeded", key=key, limit=max_requests, window=window_seconds)
        raise RateLimitExceeded(
            "Too many requests. Please try again later.",
            retry_after=window_seconds,
        )
