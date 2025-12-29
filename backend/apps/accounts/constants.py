"""
Stytch configuration constants.

These values must match the configuration in the Stytch Dashboard.
See: https://stytch.com/docs/b2b/guides/rbac/overview
"""


class StytchRoles:
    """
    Stytch RBAC role identifiers.

    These must match the role IDs configured in the Stytch Dashboard.
    """

    ADMIN = "stytch_admin"
    """Admin role ID - grants full organization management permissions."""
