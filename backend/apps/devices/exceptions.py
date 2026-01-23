"""
Exceptions for devices app.

Custom exceptions for device linking operations.
"""


class DeviceLinkError(Exception):
    """Base exception for device linking errors."""

    pass


class TokenExpiredError(DeviceLinkError):
    """Token has expired."""

    pass


class TokenUsedError(DeviceLinkError):
    """Token has already been used."""

    pass


class TokenInvalidError(DeviceLinkError):
    """Token is invalid or malformed."""

    pass


class RateLimitError(DeviceLinkError):
    """Too many link attempts."""

    pass


class DeviceAlreadyLinkedError(DeviceLinkError):
    """Device is already linked to another account."""

    pass
