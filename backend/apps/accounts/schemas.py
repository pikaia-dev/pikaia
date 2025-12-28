"""
Auth API schemas - Pydantic models for request/response.
"""

from pydantic import BaseModel, EmailStr

# --- Request Schemas ---


class MagicLinkSendRequest(BaseModel):
    """Request to send a magic link email."""

    email: EmailStr


class MagicLinkAuthenticateRequest(BaseModel):
    """Request to authenticate a magic link token."""

    token: str


class DiscoveryExchangeRequest(BaseModel):
    """Request to exchange IST for session (join existing org)."""

    intermediate_session_token: str
    organization_id: str


class DiscoveryCreateOrgRequest(BaseModel):
    """Request to create a new org from discovery flow."""

    intermediate_session_token: str
    organization_name: str
    organization_slug: str


# --- Response Schemas ---


class DiscoveredOrganization(BaseModel):
    """An organization the user can join."""

    organization_id: str
    organization_name: str
    organization_slug: str


class MagicLinkAuthenticateResponse(BaseModel):
    """Response after magic link authentication."""

    intermediate_session_token: str
    email: str
    discovered_organizations: list[DiscoveredOrganization]


class SessionResponse(BaseModel):
    """Response containing session JWT after org selection."""

    session_token: str
    session_jwt: str
    member_id: str
    organization_id: str


class MemberInfo(BaseModel):
    """Member info for /auth/me response."""

    id: int
    stytch_member_id: str
    role: str
    is_admin: bool


class OrganizationInfo(BaseModel):
    """Organization info for /auth/me response."""

    id: int
    stytch_org_id: str
    name: str
    slug: str


class UserInfo(BaseModel):
    """Current user info response."""

    id: int
    stytch_user_id: str
    email: str
    name: str


class MeResponse(BaseModel):
    """Response for /auth/me endpoint."""

    user: UserInfo
    member: MemberInfo
    organization: OrganizationInfo


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
