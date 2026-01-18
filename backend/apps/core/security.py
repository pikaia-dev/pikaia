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
from ninja.security import HttpBearer

from apps.core.auth import AuthContext


class BearerAuth(HttpBearer):
    """
    Bearer token authentication for API endpoints.

    Validates that StytchAuthMiddleware has successfully authenticated the user.
    The middleware runs first and populates request.auth if JWT is valid.
    This class provides defense-in-depth by verifying authentication succeeded.
    """

    def authenticate(self, request: HttpRequest, token: str) -> str | None:
        """
        Verify middleware authenticated the user.

        Returns token if user is authenticated, None otherwise (triggers 401).
        """
        # Check that middleware validated the JWT and set auth context
        auth: AuthContext | None = getattr(request, "auth", None)
        if auth is None or auth.user is None:
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
        # Delegate to AuthContext - raises 401/403 as appropriate
        from ninja.errors import HttpError

        auth: AuthContext | None = getattr(request, "auth", None)
        if auth is None:
            raise HttpError(401, "Not authenticated")
        auth.require_admin()
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
        request: The HTTP request (with auth from middleware)

    Returns:
        Tuple of (user, member, organization)

    Raises:
        HttpError 401: If not authenticated
    """
    from ninja.errors import HttpError

    auth: AuthContext | None = getattr(request, "auth", None)
    if auth is None:
        raise HttpError(401, "Not authenticated")
    return auth.require_auth()
