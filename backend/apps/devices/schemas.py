"""
Pydantic schemas for device API endpoints.
"""

from datetime import datetime

from ninja import Schema
from pydantic import Field


class InitiateLinkResponse(Schema):
    """Response with QR code data for device linking."""

    qr_url: str = Field(description="URL to encode in QR code (pikaia://device/link?token=...)")
    expires_at: datetime = Field(description="Token expiration timestamp")
    expires_in_seconds: int = Field(description="Seconds until token expires")


class CompleteLinkRequest(Schema):
    """Request to complete device linking."""

    token: str = Field(description="JWT token from QR code")
    device_uuid: str = Field(
        min_length=1,
        max_length=255,
        description="Unique device identifier from iOS Keychain / Android",
    )
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Device name (e.g., 'iPhone 15 Pro')",
    )
    platform: str = Field(
        min_length=1,
        max_length=20,
        description="Platform identifier (e.g., 'ios', 'android')",
    )
    os_version: str = Field(
        default="",
        max_length=20,
        description="Operating system version (e.g., '17.2')",
    )
    app_version: str = Field(
        default="",
        max_length=20,
        description="App version (e.g., '1.0.0')",
    )


class CompleteLinkResponse(Schema):
    """Response after successful device linking."""

    session_token: str = Field(description="Stytch session token (use to refresh session_jwt)")
    session_jwt: str = Field(description="Stytch session JWT for API calls (~5 min lifetime)")
    session_expires_at: datetime = Field(
        description="When the session fully expires (requires new QR scan)"
    )
    device_id: int = Field(description="Device ID")
    user_id: int = Field(description="User ID")
    member_id: str = Field(description="Stytch member ID")
    organization_id: str = Field(description="Stytch organization ID")


class DeviceResponse(Schema):
    """Single device in list response."""

    id: int
    name: str
    platform: str
    os_version: str
    app_version: str
    created_at: datetime


class DeviceListResponse(Schema):
    """Response with list of user's devices."""

    devices: list[DeviceResponse]
    count: int


class SessionRefreshRequest(Schema):
    """Request to refresh device session."""

    device_uuid: str = Field(
        min_length=1,
        max_length=255,
        description="Unique device identifier",
    )


class SessionRefreshResponse(Schema):
    """Response with refreshed session tokens."""

    session_token: str = Field(description="New Stytch session token")
    session_jwt: str = Field(description="New Stytch session JWT")
    session_expires_at: datetime = Field(description="When the session expires")
