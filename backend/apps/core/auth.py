"""
Authentication context for request lifecycle.

Provides a typed container for authentication state that middleware
populates and endpoints consume.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ninja.errors import HttpError

if TYPE_CHECKING:
    from apps.accounts.models import Member, User
    from apps.organizations.models import Organization


@dataclass
class AuthContext:
    """
    Authentication context attached to requests by StytchAuthMiddleware.

    This provides a typed container for auth state, making it easier for
    type checkers to understand and for code to access auth information.

    Attributes:
        user: The authenticated User, or None if not authenticated
        member: The Member record linking user to organization, or None
        organization: The Organization the user is acting within, or None
        failed: True if auth was attempted but failed (vs just not present)
    """

    user: "User | None" = None
    member: "Member | None" = None
    organization: "Organization | None" = None
    failed: bool = False

    @property
    def is_authenticated(self) -> bool:
        """Check if the request is fully authenticated."""
        return self.user is not None and self.member is not None and self.organization is not None

    def require_auth(self) -> tuple["User", "Member", "Organization"]:
        """
        Get authenticated context or raise 401.

        Use this in endpoints to get properly type-narrowed auth objects.
        The middleware sets all three together, so if one exists, all do.

        Returns:
            Tuple of (user, member, organization)

        Raises:
            HttpError 401: If not authenticated
        """
        if self.user is None or self.member is None or self.organization is None:
            raise HttpError(401, "Not authenticated")
        return self.user, self.member, self.organization

    def require_admin(self) -> tuple["User", "Member", "Organization"]:
        """
        Get authenticated context and verify admin role, or raise error.

        Use this in endpoints that require admin access.

        Returns:
            Tuple of (user, member, organization)

        Raises:
            HttpError 401: If not authenticated
            HttpError 403: If not an admin
        """
        user, member, org = self.require_auth()
        if not member.is_admin:
            raise HttpError(403, "Admin access required")
        return user, member, org
