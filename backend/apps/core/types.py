"""
Custom type definitions for the application.

These types help mypy understand custom attributes added by middleware.
"""

from django.http import HttpRequest

from apps.core.auth import AuthContext


class AuthenticatedHttpRequest(HttpRequest):
    """
    HttpRequest with authentication context added by StytchAuthMiddleware.

    Use this type for endpoints that require authentication.
    The middleware populates the auth attribute from JWT validation.
    """

    auth: AuthContext
