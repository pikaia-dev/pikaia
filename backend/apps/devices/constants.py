"""
Constants for devices app.

Defines enums and constants used across the devices module.
"""

from enum import StrEnum


class JWTAction(StrEnum):
    """
    JWT action claim values for device-related tokens.

    Used to identify the purpose of signed JWT tokens in the device
    linking flow.
    """

    DEVICE_LINK = "device_link"
