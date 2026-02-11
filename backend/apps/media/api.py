"""
Media API endpoints for image uploads.
"""

from ninja import File, Form, Router
from ninja.errors import HttpError
from ninja.files import UploadedFile

from apps.core.logging import get_logger
from apps.core.schemas import ErrorResponse
from apps.core.security import BearerAuth, get_auth_context
from apps.core.types import AuthenticatedHttpRequest
from apps.media.models import UploadedImage
from apps.media.schemas import (
    ConfirmUploadSchema,
    DirectUploadResponseSchema,
    ImageResponseSchema,
    UploadRequestSchema,
    UploadResponseSchema,
)
from apps.media.services import get_storage_service

logger = get_logger(__name__)

router = Router(tags=["media"])
bearer_auth = BearerAuth()


@router.post(
    "/upload-request",
    response={
        200: UploadResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        402: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="requestImageUpload",
    summary="Request an image upload URL",
)
def request_upload(
    request: AuthenticatedHttpRequest, payload: UploadRequestSchema
) -> UploadResponseSchema:
    """
    Request a presigned URL for uploading an image.

    Returns upload URL and instructions. The client should:
    1. Upload the file to the returned URL using the specified method
    2. Call /confirm endpoint after successful upload
    """
    user, _, org = get_auth_context(request)

    storage = get_storage_service()

    # Validate upload request
    errors = storage.validate_upload_request(
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        image_type=payload.image_type,
    )
    if errors:
        raise HttpError(400, "; ".join(errors))

    # Generate storage key based on image type
    owner_id = str(user.id) if payload.image_type == "avatar" else str(org.id)

    key = storage.generate_key(
        image_type=payload.image_type,
        owner_id=owner_id,
        filename=payload.filename,
    )

    # Generate upload URL
    upload_info = storage.generate_upload_url(
        key=key,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
    )

    return UploadResponseSchema(
        upload_url=upload_info.upload_url,
        method=upload_info.method,
        key=upload_info.key,
        fields=upload_info.fields,
    )


@router.post(
    "/confirm",
    response={
        200: ImageResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        402: ErrorResponse,
        404: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="confirmImageUpload",
    summary="Confirm an image upload",
)
def confirm_upload(
    request: AuthenticatedHttpRequest, payload: ConfirmUploadSchema
) -> ImageResponseSchema:
    """
    Confirm that an image was successfully uploaded.

    Verifies the file exists in storage and saves metadata to the database.
    """
    user, _, org = get_auth_context(request)

    storage = get_storage_service()

    # Verify file exists and get metadata
    metadata = storage.confirm_upload(payload.key)
    if metadata is None:
        raise HttpError(404, "File not found. The upload may have failed.")

    # Sanitize SVG files to prevent XSS (for S3 presigned uploads)
    if metadata.content_type == "image/svg+xml":
        from apps.media.svg_sanitizer import SVGSanitizationError

        try:
            # Download, sanitize, and re-upload
            sanitized_content = storage.sanitize_svg_in_storage(payload.key)
            if sanitized_content:
                # Update size after sanitization (content may have changed)
                metadata.size_bytes = len(sanitized_content)
        except SVGSanitizationError as e:
            # Delete the dangerous file
            storage.delete(payload.key)
            raise HttpError(400, f"Invalid SVG file: {e}") from e

    # Create database record
    image = UploadedImage.objects.create(
        storage_key=payload.key,
        image_type=payload.image_type,
        content_type=metadata.content_type,
        size_bytes=metadata.size_bytes,
        width=metadata.width,
        height=metadata.height,
        user=user if payload.image_type == "avatar" else None,
        organization=org if payload.image_type == "logo" else None,
        uploaded_by=user,
    )

    # Update user/org avatar/logo URL
    url = storage.get_public_url(payload.key)

    if payload.image_type == "avatar":
        user.avatar_url = url
        user.save(update_fields=["avatar_url", "updated_at"])
    else:  # logo
        org.logo_url = url
        org.save(update_fields=["logo_url", "updated_at"])
        # Sync logo to Stytch
        from apps.accounts.services import sync_logo_to_stytch

        sync_logo_to_stytch(org)

    return ImageResponseSchema(
        id=str(image.id),
        url=url,
        width=metadata.width,
        height=metadata.height,
    )


@router.post(
    "/direct-upload",
    response={
        200: DirectUploadResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        402: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="directUpload",
    summary="Direct upload for local development",
)
def direct_upload(
    request: AuthenticatedHttpRequest,
    file: UploadedFile = File(...),  # noqa: B008
    key: str = Form(""),  # noqa: B008
    content_type: str = Form(""),  # noqa: B008
) -> DirectUploadResponseSchema:
    """
    Direct file upload endpoint for local development.

    In production, files are uploaded directly to S3 using presigned URLs.
    This endpoint is only used in local development.
    """
    get_auth_context(request)  # Validates authentication

    if not key:
        raise HttpError(400, "Missing storage key")

    storage = get_storage_service()

    # Read file content
    content = file.read()

    # Determine content type
    actual_content_type = content_type or file.content_type or "application/octet-stream"

    # Sanitize SVG files to prevent XSS
    if actual_content_type == "image/svg+xml":
        from apps.media.svg_sanitizer import SVGSanitizationError, sanitize_svg

        try:
            content = sanitize_svg(content)
        except SVGSanitizationError as e:
            raise HttpError(400, f"Invalid SVG file: {e}") from e

    # Save to storage
    storage.save_file(key, content, actual_content_type)

    return DirectUploadResponseSchema(
        key=key,
        message="File uploaded successfully",
    )


@router.delete(
    "/{image_id}",
    response={
        200: dict,
        401: ErrorResponse,
        402: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="deleteImage",
    summary="Delete an uploaded image",
)
def delete_image(request: AuthenticatedHttpRequest, image_id: str) -> dict:
    """
    Delete an uploaded image.

    Users can only delete their own avatars.
    Admins can delete organization logos.
    """
    user, member, org = get_auth_context(request)

    try:
        image = UploadedImage.objects.get(id=image_id)
    except (UploadedImage.DoesNotExist, ValueError):
        raise HttpError(404, "Image not found") from None

    # Check ownership
    can_delete = False
    if (image.user_id == user.id) or (image.organization_id == org.id and member.is_admin):
        can_delete = True

    if not can_delete:
        raise HttpError(403, "You don't have permission to delete this image")

    # Delete from storage
    storage = get_storage_service()
    storage.delete(image.storage_key)

    # Clear URL from user/org if this was their current avatar/logo
    if image.image_type == "avatar" and user.avatar_url and image.storage_key in user.avatar_url:
        user.avatar_url = ""
        user.save(update_fields=["avatar_url", "updated_at"])
    elif image.image_type == "logo" and org.logo_url and image.storage_key in org.logo_url:
        org.logo_url = ""
        org.save(update_fields=["logo_url", "updated_at"])
        # Sync logo removal to Stytch
        from apps.accounts.services import sync_logo_to_stytch

        sync_logo_to_stytch(org)

    # Delete database record
    image.delete()

    return {"message": "Image deleted successfully"}
