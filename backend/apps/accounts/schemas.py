"""
Auth API schemas - Pydantic models for request/response.
"""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

# Stytch slug requirements: 2-128 chars, lowercase alphanumeric + ._~-
_SLUG_ALLOWED_CHARS = re.compile(r"[^a-z0-9._~-]+")
_SLUG_VALID_PATTERN = re.compile(r"^[a-z0-9._~-]{2,128}$")


def normalize_slug(value: str) -> str:
    """
    Normalize a slug to meet Stytch requirements.

    Transformations:
    1. Lowercase
    2. Strip whitespace
    3. Replace consecutive non-allowed chars with single hyphen
    4. Remove leading/trailing hyphens
    5. Truncate to 128 chars

    Allowed characters: a-z, 0-9, hyphen, period, underscore, tilde
    """
    slug = value.strip().lower()
    # Replace consecutive non-allowed chars with single hyphen
    slug = _SLUG_ALLOWED_CHARS.sub("-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate to max length
    slug = slug[:128]
    return slug


def validate_slug(slug: str) -> str:
    """
    Validate a normalized slug meets Stytch requirements.

    Raises ValueError if invalid.
    """
    if not _SLUG_VALID_PATTERN.match(slug):
        raise ValueError(
            "Slug must be 2-128 characters: lowercase letters, numbers, "
            "hyphens, periods, underscores, or tildes only"
        )
    return slug


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

    @field_validator("organization_slug", mode="before")
    @classmethod
    def normalize_and_validate_slug(cls, v: str) -> str:
        """Normalize slug and validate against Stytch requirements."""
        if not isinstance(v, str):
            raise ValueError("Slug must be a string")
        slug = normalize_slug(v)
        return validate_slug(slug)


class MobileProvisionRequest(BaseModel):
    """Request for mobile user provisioning (API key auth).

    Either provide organization_id to join an existing org,
    or organization_name + organization_slug to create a new one.
    """

    email: EmailStr = Field(
        ...,
        description="User's email address",
        examples=["user@example.com"],
    )
    name: str = Field(
        "",
        max_length=255,
        description="User's display name (optional)",
        examples=["Jane Doe"],
    )
    phone_number: str = Field(
        "",
        max_length=20,
        description="User's phone number in E.164 format (optional, stored unverified)",
        examples=["+14155551234"],
    )

    # Either provide organization_id to join existing, or org name/slug to create new
    organization_id: str | None = Field(
        None,
        description="Stytch org ID to join (mutually exclusive with org creation fields)",
        examples=["organization-live-abc123"],
    )
    organization_name: str | None = Field(
        None,
        max_length=255,
        description="Name for new organization (requires organization_slug)",
        examples=["Acme Corp"],
    )
    organization_slug: str | None = Field(
        None,
        description="Slug for new organization (requires organization_name)",
        examples=["acme-corp"],
    )

    @field_validator("organization_slug", mode="before")
    @classmethod
    def normalize_and_validate_slug_if_provided(cls, v: str | None) -> str | None:
        """Normalize slug and validate against Stytch requirements if provided."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Slug must be a string")
        slug = normalize_slug(v)
        return validate_slug(slug)


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
                "intermediate_session_token": "ist_xxx...",  # nosec B105
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
                "session_token": "stytch_session_xxx...",  # nosec B105
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
    role: str = Field(
        ..., description="Member's role within the organization (e.g., admin, member)"
    )
    is_admin: bool = Field(..., description="Whether the member has admin privileges")


class OrganizationInfo(BaseModel):
    """Organization info for /auth/me response."""

    id: int = Field(..., description="Local database organization ID")
    stytch_org_id: str = Field(..., description="Stytch organization ID")
    name: str = Field(..., description="Organization display name")
    slug: str = Field(..., description="URL-safe organization identifier")
    logo_url: str = Field("", description="URL to organization logo image")


class UserInfo(BaseModel):
    """Current user info response."""

    id: int = Field(..., description="Local database user ID")
    email: str = Field(..., description="User's email address")
    name: str = Field(..., description="User's display name")
    avatar_url: str = Field("", description="URL to user's avatar image")
    phone_number: str = Field("", description="Phone number in E.164 format")


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

    model_config = {
        "json_schema_extra": {"example": {"message": "Operation completed successfully."}}
    }


# --- Settings Schemas ---


class UpdateProfileRequest(BaseModel):
    """Request to update user profile (name only).

    Phone number changes require OTP verification via /phone/verify-otp.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's display name",
        examples=["Jane Doe"],
    )


class SendPhoneOtpRequest(BaseModel):
    """Request to send OTP to a phone number for verification."""

    phone_number: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="Phone number in E.164 format",
        examples=["+14155551234"],
    )

    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number is in E.164 format."""
        v = v.strip()
        if not v.startswith("+"):
            raise ValueError("Phone number must start with +")
        if not v[1:].isdigit():
            raise ValueError("Phone number must contain only digits after +")
        if len(v) < 8 or len(v) > 16:
            raise ValueError("Phone number must be 8-16 characters")
        return v


class VerifyPhoneOtpRequest(BaseModel):
    """Request to verify a phone OTP."""

    phone_number: str = Field(
        ...,
        description="Phone number that received the OTP",
    )
    otp_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit OTP code",
        examples=["123456"],
    )


class PhoneOtpResponse(BaseModel):
    """Response for phone OTP operations."""

    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Status message")


class StartEmailUpdateRequest(BaseModel):
    """Request to start email update flow."""

    new_email: EmailStr = Field(
        ...,
        description="New email address to change to",
        examples=["newemail@example.com"],
    )


class EmailUpdateResponse(BaseModel):
    """Response for email update initiation."""

    success: bool = Field(..., description="Whether the update was initiated")
    message: str = Field(..., description="Status message")


class UpdateOrganizationRequest(BaseModel):
    """Request to update organization settings (admin only)."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Organization display name",
        examples=["Acme Corp"],
    )
    slug: str | None = Field(
        None,
        description="URL-safe identifier for the organization (2-128 chars, lowercase)",
        examples=["acme-corp"],
    )

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_and_validate_slug(cls, v: str | None) -> str | None:
        """Normalize slug and validate against Stytch requirements."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Slug must be a string")
        slug = normalize_slug(v)
        return validate_slug(slug)


class BillingAddressSchema(BaseModel):
    """Billing address for organization."""

    line1: str = Field("", max_length=255, description="Street address line 1")
    line2: str = Field("", max_length=255, description="Street address line 2")
    city: str = Field("", max_length=100, description="City")
    state: str = Field("", max_length=100, description="State/Province/Region")
    postal_code: str = Field("", max_length=20, description="Postal/ZIP code")
    country: str = Field(
        "",
        max_length=2,
        description="ISO 3166-1 alpha-2 country code",
        examples=["US", "DE", "PL"],
    )


class UpdateBillingRequest(BaseModel):
    """Request to update organization billing info (admin only)."""

    use_billing_email: bool = Field(
        False,
        description="If True, send invoices to billing_email; otherwise send to admin",
    )
    billing_email: EmailStr | None = Field(
        None,
        description="Email for invoices (used only if use_billing_email is True)",
        examples=["billing@company.com"],
    )
    billing_name: str = Field(
        "",
        max_length=255,
        description="Legal/company name for invoices",
        examples=["Acme Corporation Inc."],
    )
    address: BillingAddressSchema | None = Field(
        None,
        description="Billing address",
    )
    vat_id: str = Field(
        "",
        max_length=50,
        description="EU VAT number",
        examples=["DE123456789"],
    )


class BillingInfoResponse(BaseModel):
    """Organization billing info response."""

    use_billing_email: bool = Field(
        ..., description="If True, invoices sent to billing_email; otherwise to admin"
    )
    billing_email: str = Field(..., description="Email for invoices")
    billing_name: str = Field(..., description="Legal/company name")
    address: BillingAddressSchema = Field(..., description="Billing address")
    vat_id: str = Field(..., description="EU VAT number")


class OrganizationDetailResponse(BaseModel):
    """Full organization details response."""

    id: int = Field(..., description="Local database ID")
    stytch_org_id: str = Field(..., description="Stytch organization ID")
    name: str = Field(..., description="Organization display name")
    slug: str = Field(..., description="URL-safe identifier")
    logo_url: str = Field("", description="URL to organization logo image")
    billing: BillingInfoResponse = Field(..., description="Billing information")


# --- Member Management Schemas ---


class InviteMemberRequest(BaseModel):
    """Request to invite a new member to the organization."""

    email: EmailStr = Field(
        ...,
        description="Email address of the member to invite",
        examples=["newuser@example.com"],
    )
    name: str = Field(
        "",
        max_length=255,
        description="Optional display name for the member",
        examples=["Jane Doe"],
    )
    role: str = Field(
        "member",
        pattern="^(admin|member)$",
        description="Role to assign: 'admin' or 'member'",
        examples=["member"],
    )


class UpdateMemberRoleRequest(BaseModel):
    """Request to update a member's role."""

    role: str = Field(
        ...,
        pattern="^(admin|member)$",
        description="New role: 'admin' or 'member'",
        examples=["admin"],
    )


class MemberListItem(BaseModel):
    """Member info for list response."""

    id: int = Field(..., description="Local database member ID")
    stytch_member_id: str = Field(..., description="Stytch member ID")
    email: str = Field(..., description="Member's email address")
    name: str = Field(..., description="Member's display name")
    role: str = Field(..., description="Member's role (admin or member)")
    is_admin: bool = Field(..., description="Whether member has admin privileges")
    status: str = Field(..., description="Member status (active, invited)")
    created_at: str = Field(..., description="When the member joined (ISO format)")


class MemberListResponse(BaseModel):
    """Response containing list of organization members with pagination."""

    members: list[MemberListItem] = Field(..., description="List of active organization members")
    total: int = Field(..., description="Total number of members in the organization")
    offset: int = Field(default=0, description="Current offset for pagination")
    limit: int | None = Field(default=None, description="Limit per page (null means all)")


class InviteMemberResponse(BaseModel):
    """Response after inviting a member."""

    message: str = Field(..., description="Success message")
    stytch_member_id: str = Field(..., description="Stytch member ID of invited member")


# --- Directory Search Schemas ---


class DirectoryUserSchema(BaseModel):
    """A user from Google Workspace directory search."""

    email: str = Field(..., description="User's email address")
    name: str = Field(..., description="User's display name")
    avatar_url: str = Field("", description="URL to user's avatar image")


# --- Bulk Invite Schemas ---


class BulkInviteMemberItem(BaseModel):
    """Single member to invite in bulk operation."""

    email: EmailStr = Field(
        ...,
        description="Email address of the member to invite",
        examples=["user@example.com"],
    )
    name: str = Field(
        "",
        max_length=255,
        description="Optional display name",
        examples=["Jane Doe"],
    )
    phone: str = Field(
        "",
        max_length=20,
        description="Optional phone number in E.164 format (stored unverified)",
        examples=["+14155551234"],
    )
    role: str = Field(
        "member",
        pattern="^(admin|member)$",
        description="Role to assign: 'admin' or 'member'",
        examples=["member"],
    )

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone_if_provided(cls, v: str) -> str:
        """Validate phone number format if provided."""
        if not v:
            return ""
        v = v.strip()
        # Basic E.164 format validation
        if not v.startswith("+"):
            raise ValueError("Phone number must start with +")
        if not v[1:].replace(" ", "").replace("-", "").isdigit():
            raise ValueError("Phone number must contain only digits after +")
        # Strip spaces/dashes for storage
        return "+" + "".join(c for c in v[1:] if c.isdigit())


class BulkInviteRequest(BaseModel):
    """Request to invite multiple members at once."""

    members: list[BulkInviteMemberItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of members to invite (max 100)",
    )


class BulkInviteResultItem(BaseModel):
    """Result of a single member invite in bulk operation."""

    email: str = Field(..., description="Email address attempted")
    success: bool = Field(..., description="Whether the invite succeeded")
    error: str | None = Field(None, description="Error message if failed")
    stytch_member_id: str | None = Field(None, description="Stytch member ID if succeeded")


class BulkInviteResponse(BaseModel):
    """Response for bulk invite operation."""

    results: list[BulkInviteResultItem] = Field(..., description="Results for each member")
    total: int = Field(..., description="Total members processed")
    succeeded: int = Field(..., description="Number of successful invites")
    failed: int = Field(..., description="Number of failed invites")
