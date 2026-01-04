"""
Core schemas - shared Pydantic models for API responses.
"""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response format."""

    detail: str = Field(..., description="Human-readable error message")

    model_config = {"json_schema_extra": {"example": {"detail": "Invalid or expired token."}}}
