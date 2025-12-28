"""
Auth API schemas - Pydantic models for request/response.
"""

from pydantic import BaseModel, EmailStr, Field

# --- Request Schemas ---


class MagicLinkSendRequest(BaseModel):
    """Request to send a magic link email."""

    email: EmailStr = Field(
        ...,
        description="User's email address for magic link delivery",
        examples=["user@company.com"],
    )


class MagicLinkAuthenticateRequest(BaseModel):
    """Request to authenticate a magic link token."""

    token: str = Field(
        ...,
        description="Magic link token from the email URL query parameter",
        examples=["DOYoip3rvIMMW2A7LRLI4M3EjcxZ..."],
    )


class DiscoveryExchangeRequest(BaseModel):
    """Request to exchange IST for session (join existing org)."""

    intermediate_session_token: str = Field(
        ...,
        description="Intermediate session token from magic link authentication",
        examples=["ist_xxx..."],
    )
    organization_id: str = Field(
        ...,
        description="Stytch organization ID to join",
        examples=["organization-live-abc123..."],
    )


class DiscoveryCreateOrgRequest(BaseModel):
    """Request to create a new org from discovery flow."""

    intermediate_session_token: str = Field(
        ...,
        description="Intermediate session token from magic link authentication",
        examples=["ist_xxx..."],
    )
    organization_name: str = Field(
        ...,
        description="Display name for the new organization",
        examples=["Acme Corp"],
    )
    organization_slug: str = Field(
        ...,
        description="URL-safe identifier for the organization (lowercase, hyphens allowed)",
        examples=["acme-corp"],
    )


# --- Response Schemas ---


class DiscoveredOrganization(BaseModel):
    """An organization the user can join."""

    organization_id: str = Field(..., description="Stytch organization ID")
    organization_name: str = Field(..., description="Organization display name")
    organization_slug: str = Field(..., description="URL-safe organization identifier")


class MagicLinkAuthenticateResponse(BaseModel):
    """Response after magic link authentication."""

    intermediate_session_token: str = Field(
        ...,
        description="Token to exchange for a full session after org selection",
    )
    email: str = Field(..., description="Authenticated user's email address")
    discovered_organizations: list[DiscoveredOrganization] = Field(
        ...,
        description="Organizations the user can join or already belongs to",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "intermediate_session_token": "ist_xxx...",
                "email": "user@company.com",
                "discovered_organizations": [
                    {
                        "organization_id": "organization-live-abc123",
                        "organization_name": "Acme Corp",
                        "organization_slug": "acme-corp",
                    }
                ],
            }
        }
    }


class SessionResponse(BaseModel):
    """Response containing session credentials after org selection."""

    session_token: str = Field(..., description="Stytch session token for server-side use")
    session_jwt: str = Field(
        ...,
        description="JWT for Authorization header (Bearer token)",
    )
    member_id: str = Field(..., description="Stytch member ID within the organization")
    organization_id: str = Field(..., description="Stytch organization ID")

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_token": "stytch_session_xxx...",
                "session_jwt": "eyJhbGciOiJSUzI1NiI...",
                "member_id": "member-live-abc123",
                "organization_id": "organization-live-abc123",
            }
        }
    }


class MemberInfo(BaseModel):
    """Member info for /auth/me response."""

    id: int = Field(..., description="Local database member ID")
    stytch_member_id: str = Field(..., description="Stytch member ID")
    role: str = Field(..., description="Member's role within the organization (e.g., admin, member)")
    is_admin: bool = Field(..., description="Whether the member has admin privileges")


class OrganizationInfo(BaseModel):
    """Organization info for /auth/me response."""

    id: int = Field(..., description="Local database organization ID")
    stytch_org_id: str = Field(..., description="Stytch organization ID")
    name: str = Field(..., description="Organization display name")
    slug: str = Field(..., description="URL-safe organization identifier")


class UserInfo(BaseModel):
    """Current user info response."""

    id: int = Field(..., description="Local database user ID")
    email: str = Field(..., description="User's email address")
    name: str = Field(..., description="User's display name")


class MeResponse(BaseModel):
    """Response for /auth/me endpoint with current session context."""

    user: UserInfo = Field(..., description="Cross-org user identity")
    member: MemberInfo = Field(..., description="Org-scoped membership details")
    organization: OrganizationInfo = Field(..., description="Current organization context")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user": {"id": 1, "email": "user@company.com", "name": "Jane Doe"},
                "member": {
                    "id": 1,
                    "stytch_member_id": "member-live-abc123",
                    "role": "admin",
                    "is_admin": True,
                },
                "organization": {
                    "id": 1,
                    "stytch_org_id": "organization-live-abc123",
                    "name": "Acme Corp",
                    "slug": "acme-corp",
                },
            }
        }
    }


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str = Field(..., description="Human-readable status message")

    model_config = {"json_schema_extra": {"example": {"message": "Operation completed successfully."}}}
