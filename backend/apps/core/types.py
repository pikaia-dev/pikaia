"""
Custom type definitions for the application.

These types help mypy understand custom attributes added by middleware.
"""

from typing import TYPE_CHECKING

from django.http import HttpRequest

if TYPE_CHECKING:
    from apps.accounts.models import Member, User
    from apps.organizations.models import Organization


class AuthenticatedHttpRequest(HttpRequest):
    """
    HttpRequest with authentication context added by StytchAuthMiddleware.

    Use this type for endpoints that require authentication.
    The middleware populates these attributes from JWT validation.
    """

    auth_user: "User | None"
    auth_member: "Member | None"
    auth_organization: "Organization | None"
    auth_failed: bool
