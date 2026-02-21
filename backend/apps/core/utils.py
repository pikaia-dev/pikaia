"""
Core utility functions.
"""

from typing import cast, overload

from django.http import HttpRequest


@overload
def get_client_ip(request: HttpRequest) -> str | None: ...


@overload
def get_client_ip(request: HttpRequest, default: str) -> str: ...


def get_client_ip(request: HttpRequest, default: str | None = None) -> str | None:
    """
    Extract client IP from X-Forwarded-For or REMOTE_ADDR.

    Handles the case where X-Forwarded-For contains multiple IPs
    (from proxy chain) by taking the first (original client).

    Args:
        request: The Django HTTP request.
        default: Fallback value when no IP can be determined.
            Defaults to None.

    Returns:
        The client IP address, or default if not available.
    """
    x_forwarded_for: str | None = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    remote_addr = cast(str | None, request.META.get("REMOTE_ADDR"))
    if remote_addr is not None:
        return remote_addr
    return default


def normalize_email(email: str) -> str:
    """Normalize an email address for case-insensitive comparison.

    Strips whitespace and lowercases the entire address.
    """
    return email.strip().lower()


def extract_bearer_token(request: HttpRequest) -> str | None:
    """
    Extract token from Authorization: Bearer header.

    Args:
        request: The Django HTTP request.

    Returns:
        The bearer token string, or None if no valid Bearer header present.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ")
    return None
