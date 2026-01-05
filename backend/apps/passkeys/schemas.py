"""
Pydantic schemas for passkey API endpoints.
"""

from pydantic import BaseModel, Field


# --- Registration ---


class PasskeyRegistrationOptionsRequest(BaseModel):
    """Request for passkey registration options."""

    # No fields needed - user comes from auth context
    pass


class PasskeyRegistrationOptionsResponse(BaseModel):
    """Response with registration options for WebAuthn."""

    challenge_id: str = Field(description="Challenge ID to include in verification request")
    options: dict = Field(description="WebAuthn registration options for navigator.credentials.create()")


class PasskeyRegistrationVerifyRequest(BaseModel):
    """Request to verify passkey registration."""

    challenge_id: str = Field(description="Challenge ID from registration options")
    credential: dict = Field(description="Credential response from navigator.credentials.create()")
    name: str = Field(
        min_length=1,
        max_length=100,
        description="User-friendly name for the passkey (e.g., 'iPhone 15')",
    )


class PasskeyRegistrationVerifyResponse(BaseModel):
    """Response after successful passkey registration."""

    id: int = Field(description="Passkey ID")
    name: str = Field(description="Passkey name")
    created_at: str = Field(description="Creation timestamp")


# --- Authentication ---


class PasskeyAuthenticationOptionsRequest(BaseModel):
    """Request for passkey authentication options."""

    email: str | None = Field(
        default=None,
        description="Optional email to filter allowed credentials",
    )


class PasskeyAuthenticationOptionsResponse(BaseModel):
    """Response with authentication options for WebAuthn."""

    challenge_id: str = Field(description="Challenge ID to include in verification request")
    options: dict = Field(description="WebAuthn authentication options for navigator.credentials.get()")


class PasskeyAuthenticationVerifyRequest(BaseModel):
    """Request to verify passkey authentication."""

    challenge_id: str = Field(description="Challenge ID from authentication options")
    credential: dict = Field(description="Credential response from navigator.credentials.get()")
    organization_id: str | None = Field(
        default=None,
        description="Organization ID to authenticate into",
    )


class PasskeyAuthenticationVerifyResponse(BaseModel):
    """Response after successful passkey authentication."""

    session_token: str = Field(description="Stytch session token")
    session_jwt: str = Field(description="Stytch session JWT")
    member_id: str = Field(description="Member ID")
    organization_id: str = Field(description="Organization ID")
    user_id: int = Field(description="User ID")


# --- Management ---


class PasskeyListItem(BaseModel):
    """Single passkey in the list response."""

    id: int
    name: str
    created_at: str
    last_used_at: str | None
    backup_eligible: bool
    backup_state: bool


class PasskeyListResponse(BaseModel):
    """Response with list of user's passkeys."""

    passkeys: list[PasskeyListItem]


class PasskeyDeleteResponse(BaseModel):
    """Response after deleting a passkey."""

    success: bool = True
    message: str = "Passkey deleted successfully"
