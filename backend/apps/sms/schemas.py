"""
Schemas for SMS/OTP endpoints.
"""

from pydantic import BaseModel, Field


class SendOTPRequest(BaseModel):
    """Request to send OTP to a phone number."""

    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Phone number in E.164 format (e.g., +14155551234)",
        examples=["+14155551234"],
    )


class SendOTPResponse(BaseModel):
    """Response after sending OTP."""

    success: bool
    message: str
    expires_in_minutes: int = Field(
        description="Minutes until the OTP expires",
    )


class VerifyOTPRequest(BaseModel):
    """Request to verify an OTP code."""

    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=20,
        description="Phone number in E.164 format",
        examples=["+14155551234"],
    )
    code: str = Field(
        ...,
        min_length=4,
        max_length=10,
        description="The OTP code received via SMS",
        examples=["1234"],
    )


class VerifyOTPResponse(BaseModel):
    """Response after successful OTP verification."""

    success: bool
    message: str
    phone_verified: bool = Field(
        description="Whether the phone is now verified for the user",
    )
