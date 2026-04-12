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

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from django.conf import settings as django_settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse

from apps.core.logging import get_logger
from apps.core.utils import get_client_ip

P = ParamSpec("P")
T = TypeVar("T")

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

    Uses a sliding window: each request resets the TTL to ``window_seconds``
    from now. The counter resets once no requests arrive within the window.

    We avoid ``cache.incr()`` because Django's ``DatabaseCache.incr()``
    calls ``set()`` without a timeout, resetting the TTL to the cache
    default (300 s) and causing counters to accumulate indefinitely.

    Args:
        key: Cache key identifying the rate limit bucket
            (e.g., "magic_link_send:user@example.com").
        max_requests: Maximum allowed requests within the window.
        window_seconds: Time window in seconds.

    Raises:
        RateLimitExceeded: If the limit has been reached.
    """
    cache_key = f"rate_limit:{key}"
    current = cache.get(cache_key)

    if current is None:
        cache.set(cache_key, 1, timeout=window_seconds)
        return

    if current >= max_requests:
        logger.warning("rate_limit_exceeded", key=key, limit=max_requests, window=window_seconds)
        raise RateLimitExceeded(
            "Too many requests. Please try again later.",
            retry_after=window_seconds,
        )

    cache.set(cache_key, current + 1, timeout=window_seconds)


def peek_rate_limit(
    key: str,
    *,
    max_requests: int,
    window_seconds: int,
) -> None:
    """
    Check whether a rate limit has been exceeded **without** incrementing.

    Useful when the caller wants to gate entry to an operation but only
    count it as a "request" on certain code paths (e.g. failed attempts).

    Args:
        key: Cache key identifying the rate limit bucket.
        max_requests: Maximum allowed requests within the window.
        window_seconds: Time window in seconds.

    Raises:
        RateLimitExceeded: If the limit has already been reached.
    """
    cache_key = f"rate_limit:{key}"
    current = cache.get(cache_key)

    if current is not None and current >= max_requests:
        logger.warning("rate_limit_exceeded", key=key, limit=max_requests, window=window_seconds)
        raise RateLimitExceeded(
            "Too many requests. Please try again later.",
            retry_after=window_seconds,
        )


def increment_rate_limit(
    key: str,
    *,
    window_seconds: int,
) -> None:
    """
    Increment a rate limit counter **without** checking the limit.

    Meant to be paired with ``peek_rate_limit`` so the caller can
    increment only on specific code paths (e.g. failed verification
    attempts).

    Args:
        key: Cache key identifying the rate limit bucket.
        window_seconds: Time window in seconds.
    """
    cache_key = f"rate_limit:{key}"
    current = cache.get(cache_key)

    if current is None:
        cache.set(cache_key, 1, timeout=window_seconds)
    else:
        cache.set(cache_key, current + 1, timeout=window_seconds)


def rate_limit_ip_django_view(
    namespace: str,
    max_requests_setting: str,
    window_seconds_setting: str,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that applies IP-based rate limiting to a plain Django view.

    Unlike ``rate_limit_ip`` (which raises ``HttpError`` for Django Ninja),
    this returns an ``HttpResponse(status=429)`` with a ``Retry-After``
    header, suitable for raw Django views like webhook receivers.

    Args:
        namespace: Prefix for the cache key (e.g. ``"stripe_webhook"``).
        max_requests_setting: Django setting name for the request cap.
        window_seconds_setting: Django setting name for the time window.

    Example::

        @csrf_exempt
        @require_POST
        @rate_limit_ip_django_view(
            "stripe_webhook",
            "WEBHOOK_RATE_LIMIT_STRIPE_PER_IP",
            "WEBHOOK_RATE_LIMIT_WINDOW",
        )
        def stripe_webhook(request):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            request = args[0]
            if not isinstance(request, HttpRequest):
                raise TypeError(f"Expected HttpRequest, got {type(request).__name__}")
            client_ip = get_client_ip(request, default="unknown")
            key = f"{namespace}:ip:{client_ip}"
            max_requests = getattr(django_settings, max_requests_setting)
            window_seconds = getattr(django_settings, window_seconds_setting)
            try:
                check_rate_limit(key, max_requests=max_requests, window_seconds=window_seconds)
            except RateLimitExceeded as e:
                response = HttpResponse(
                    "Too many requests. Please try again later.",
                    status=429,
                    content_type="text/plain",
                )
                response["Retry-After"] = str(e.retry_after)
                return response  # type: ignore[return-value]
            return func(*args, **kwargs)

        return wrapper

    return decorator
