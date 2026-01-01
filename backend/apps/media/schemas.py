"""
Media API schemas - Pydantic models for request/response.
"""

from pydantic import BaseModel, Field


class UploadRequestSchema(BaseModel):
    """Request to initiate an image upload."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename with extension",
        examples=["avatar.jpg"],
    )
    content_type: str = Field(
        ...,
        description="MIME type of the image",
        examples=["image/jpeg", "image/png", "image/webp"],
    )
    size_bytes: int = Field(
        ...,
        gt=0,
        description="File size in bytes",
        examples=[102400],
    )
    image_type: str = Field(
        ...,
        pattern="^(avatar|logo)$",
        description="Type of image: 'avatar' or 'logo'",
        examples=["avatar"],
    )


class UploadResponseSchema(BaseModel):
    """Response with upload URL and instructions."""

    upload_url: str = Field(..., description="URL to upload the file to")
    method: str = Field(..., description="HTTP method to use (PUT or POST)")
    key: str = Field(..., description="Storage key for the file")
    fields: dict[str, str] = Field(
        default_factory=dict,
        description="Additional form fields for POST uploads",
    )


class ConfirmUploadSchema(BaseModel):
    """Request to confirm an upload was completed."""

    key: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Storage key from the upload response",
    )
    image_type: str = Field(
        ...,
        pattern="^(avatar|logo)$",
        description="Type of image: 'avatar' or 'logo'",
    )


class ImageResponseSchema(BaseModel):
    """Response with uploaded image details."""

    id: str = Field(..., description="Image UUID")
    url: str = Field(..., description="Public URL to access the image")
    width: int | None = Field(None, description="Image width in pixels")
    height: int | None = Field(None, description="Image height in pixels")


class DirectUploadResponseSchema(BaseModel):
    """Response after direct local upload."""

    key: str = Field(..., description="Storage key of the uploaded file")
    message: str = Field(..., description="Success message")
