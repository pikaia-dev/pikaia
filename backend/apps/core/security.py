"""
Core security - authentication classes for API.
"""

from ninja.security import HttpBearer


class BearerAuth(HttpBearer):
    """
    Bearer token authentication for API endpoints.

    Validates presence of JWT token in Authorization header.
    Actual JWT validation is performed by StytchAuthMiddleware.
    This class provides OpenAPI security scheme documentation.
    """

    def authenticate(self, request, token: str) -> str | None:
        """
        Check token exists. Middleware handles actual validation.

        Returns token if present, None otherwise (triggers 401).
        """
        return token if token else None
