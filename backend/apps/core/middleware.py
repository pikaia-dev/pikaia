"""
Core middleware.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from django.http import HttpRequest, HttpResponse

if TYPE_CHECKING:
    from apps.accounts.models import Member
    from apps.organizations.models import Organization


class TenantContextMiddleware:
    """
    Extracts organization context from authenticated request.
    
    Sets request.organization and request.member for use in views and services.
    The actual JWT parsing will be implemented with Stytch integration.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Initialize tenant context (will be populated by auth middleware)
        request.organization: Organization | None = None  # type: ignore[attr-defined]
        request.member: Member | None = None  # type: ignore[attr-defined]

        # TODO: Extract org/member from JWT claims after Stytch integration
        # The auth middleware will decode the JWT and look up the org/member

        return self.get_response(request)
