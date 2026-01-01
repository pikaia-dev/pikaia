"""
Core security - authentication classes for API.
"""

from django.http import HttpRequest
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

