"""
Core security - authentication and authorization for API.
"""

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.accounts.models import Member, User
    from apps.organizations.models import Organization

from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import HttpBearer


class BearerAuth(HttpBearer):
    """
    Bearer token authentication for API endpoints.

    Validates that StytchAuthMiddleware has successfully authenticated the user.
    The middleware runs first and populates request.auth_user if JWT is valid.
    This class provides defense-in-depth by verifying authentication succeeded.
    """

    def authenticate(self, request: HttpRequest, token: str) -> str | None:
        """
        Verify middleware authenticated the user.

        Returns token if user is authenticated, None otherwise (triggers 401).
        """
        # Check that middleware validated the JWT and set auth context
        if not hasattr(request, "auth_user") or request.auth_user is None:
            return None

        return token


def require_admin[F: Callable[..., Any]](func: F) -> F:
    """
    Decorator that enforces admin role for an endpoint.

    Use this on any endpoint that should be restricted to organization admins.
    Must be applied AFTER @router.get/post/etc (decorators execute bottom-up).

    Example:
        @router.post("/billing/checkout")
        @require_admin
        def create_checkout(request: HttpRequest) -> CheckoutResponse:
            ...

    Raises:
        HttpError(401): If user is not authenticated
        HttpError(403): If user is not an admin
    """

    @wraps(func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        # Check authentication - middleware sets auth_user, auth_member, and
        # auth_organization together, so checking any one of them is sufficient.
        # We check auth_member since we need it for the admin role check anyway.
        if not hasattr(request, "auth_member") or request.auth_member is None:
            raise HttpError(401, "Not authenticated")

        # Check admin role (safe to access - we verified auth_member is not None above)
        if not request.auth_member.is_admin:
            raise HttpError(403, "Admin access required")

        return func(request, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def get_auth_context(
    request: HttpRequest,
) -> tuple["User", "Member", "Organization"]:
    """
    Get authenticated user, member, and organization from request.

    Use this helper to get properly type-narrowed auth context in endpoints.
    The middleware sets all three together, so if one exists, all do.

    Args:
        request: The HTTP request (with auth attrs from middleware)

    Returns:
        Tuple of (user, member, organization)

    Raises:
        HttpError 401: If not authenticated
    """

    if not hasattr(request, "auth_user") or request.auth_user is None:
        raise HttpError(401, "Not authenticated")

    # Middleware sets all three together (attrs added dynamically)
    assert request.auth_member is not None  # type: ignore[attr-defined]
    assert request.auth_organization is not None  # type: ignore[attr-defined]

    return (
        request.auth_user,
        request.auth_member,  # type: ignore[attr-defined]
        request.auth_organization,  # type: ignore[attr-defined]
    )
