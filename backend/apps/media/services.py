"""
Storage service abstraction for local and S3 backends.
"""

import mimetypes
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from PIL import Image

from apps.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UploadInfo:
    """Information for uploading a file."""

    upload_url: str
    method: str  # "PUT" for S3 presigned, "POST" for local direct
    key: str
    fields: dict[str, str]  # Additional form fields for POST (presigned POST)


@dataclass
class ImageMetadata:
    """Metadata extracted from an uploaded image."""

    content_type: str
    size_bytes: int
    width: int
    height: int


class StorageService:
    """
    Abstraction over local filesystem and S3 storage.

    In production, generates presigned URLs for direct S3 uploads.
    In development, provides a direct upload endpoint.
    """

    # Upload limits from settings
    MAX_IMAGE_SIZE_BYTES: int = getattr(settings, "MEDIA_MAX_IMAGE_SIZE_BYTES", 10 * 1024 * 1024)
    ALLOWED_CONTENT_TYPES: set[str] = set(
        getattr(
            settings,
            "MEDIA_ALLOWED_IMAGE_TYPES",
            ["image/jpeg", "image/png", "image/webp", "image/svg+xml", "image/avif"],
        )
    )
    PRESIGNED_URL_EXPIRY = 300  # 5 minutes

    def __init__(self) -> None:
        self.use_s3 = getattr(settings, "USE_S3_STORAGE", False)
        if self.use_s3:
            import boto3

            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
            )
            self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    def generate_key(self, image_type: str, owner_id: str, filename: str) -> str:
        """Generate a unique storage key for an image."""
        ext = Path(filename).suffix.lower() or ".jpg"
        unique_id = uuid.uuid4().hex[:12]
        return f"{image_type}s/{owner_id}/{unique_id}{ext}"

    def get_max_size(self, image_type: str) -> int:
        """Get maximum allowed size for an image type."""
        # Unified 10MB limit for all image types
        return self.MAX_IMAGE_SIZE_BYTES

    def validate_upload_request(
        self, content_type: str, size_bytes: int, image_type: str
    ) -> list[str]:
        """
        Validate upload request parameters.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        if content_type not in self.ALLOWED_CONTENT_TYPES:
            allowed = ", ".join(sorted(self.ALLOWED_CONTENT_TYPES))
            errors.append(f"Invalid content type. Allowed: {allowed}")

        max_size = self.get_max_size(image_type)
        if size_bytes > max_size:
            max_mb = max_size / (1024 * 1024)
            errors.append(f"File too large. Maximum size: {max_mb:.0f}MB")

        return errors

    def generate_upload_url(
        self,
        key: str,
        content_type: str,
        size_bytes: int,
    ) -> UploadInfo:
        """
        Generate upload URL for a file.

        For S3: Returns presigned PUT URL
        For local: Returns direct upload endpoint URL
        """
        if self.use_s3:
            return self._generate_s3_presigned_url(key, content_type, size_bytes)
        return self._generate_local_upload_info(key, content_type)

    def _generate_s3_presigned_url(
        self,
        key: str,
        content_type: str,
        size_bytes: int,
    ) -> UploadInfo:
        """Generate S3 presigned PUT URL."""
        presigned_url = self.s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": size_bytes,
            },
            ExpiresIn=self.PRESIGNED_URL_EXPIRY,
        )

        return UploadInfo(
            upload_url=presigned_url,
            method="PUT",
            key=key,
            fields={},
        )

    def _generate_local_upload_info(self, key: str, content_type: str) -> UploadInfo:
        """Generate local direct upload endpoint info."""
        # The frontend will POST to our direct upload endpoint
        base_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")
        return UploadInfo(
            upload_url=f"{base_url}/api/v1/media/direct-upload",
            method="POST",
            key=key,
            fields={"content_type": content_type},
        )

    def confirm_upload(self, key: str) -> ImageMetadata | None:
        """
        Verify file exists and extract metadata.

        Returns None if file doesn't exist.
        """
        if self.use_s3:
            return self._confirm_s3_upload(key)
        return self._confirm_local_upload(key)

    def _confirm_s3_upload(self, key: str) -> ImageMetadata | None:
        """Confirm S3 upload and get metadata."""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            size_bytes = response["ContentLength"]
            content_type = response["ContentType"]

            # Download to get dimensions
            obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            image_data = obj["Body"].read()

            width, height = self._get_image_dimensions(image_data)

            return ImageMetadata(
                content_type=content_type,
                size_bytes=size_bytes,
                width=width,
                height=height,
            )
        except Exception as e:
            logger.warning("Failed to confirm S3 upload for key %s: %s", key, e)
            return None

    def _confirm_local_upload(self, key: str) -> ImageMetadata | None:
        """Confirm local upload and get metadata."""
        try:
            if not default_storage.exists(key):
                return None

            size_bytes = default_storage.size(key)
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

            # Read file to get dimensions
            with default_storage.open(key, "rb") as f:
                image_data = f.read()

            width, height = self._get_image_dimensions(image_data)

            return ImageMetadata(
                content_type=content_type,
                size_bytes=size_bytes,
                width=width,
                height=height,
            )
        except Exception as e:
            logger.warning("Failed to confirm local upload for key %s: %s", key, e)
            return None

    def _get_image_dimensions(self, image_data: bytes) -> tuple[int, int]:
        """Extract image dimensions from binary data."""
        try:
            with Image.open(BytesIO(image_data)) as img:
                return img.size
        except Exception:
            return (0, 0)

    def save_file(self, key: str, content: bytes, content_type: str) -> None:
        """
        Save file to storage (used for local direct uploads).
        """
        if self.use_s3:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        else:
            default_storage.save(key, BytesIO(content))

    def delete(self, key: str) -> None:
        """Delete file from storage."""
        try:
            if self.use_s3:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            else:
                if default_storage.exists(key):
                    default_storage.delete(key)
        except Exception as e:
            logger.warning("Failed to delete file %s: %s", key, e)

    def sanitize_svg_in_storage(self, key: str) -> bytes | None:
        """
        Sanitize an SVG file that's already in storage.

        Downloads the file, sanitizes it, and re-uploads.
        Used for S3 presigned uploads where we can't sanitize on the way in.

        Returns the sanitized content bytes, or None if not an SVG.
        Raises SVGSanitizationError if sanitization fails.
        """
        from apps.media.svg_sanitizer import sanitize_svg

        # Download the file
        if self.use_s3:
            obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            content = obj["Body"].read()
            content_type = obj.get("ContentType", "")
        else:
            if not default_storage.exists(key):
                return None
            with default_storage.open(key, "rb") as f:
                content = f.read()
            content_type = mimetypes.guess_type(key)[0] or ""

        # Only sanitize SVGs
        if content_type != "image/svg+xml" and not key.lower().endswith(".svg"):
            return None

        # Sanitize (may raise SVGSanitizationError)
        sanitized_content = sanitize_svg(content)

        # Re-upload sanitized version
        self.save_file(key, sanitized_content, "image/svg+xml")

        return sanitized_content

    def get_public_url(self, key: str) -> str:
        """Get public URL for a file (original size)."""
        return self.get_image_url(key)

    def get_image_url(
        self,
        key: str,
        width: int | None = None,
        height: int | None = None,
        fit: str | None = None,
    ) -> str:
        """
        Get URL for an image with optional transformations.

        Compatible with AWS Dynamic Image Transformation for CloudFront:
        https://aws.amazon.com/solutions/implementations/dynamic-image-transformation-for-amazon-cloudfront/

        When IMAGE_TRANSFORM_URL is configured, generates URLs like:
            https://transform.example.com/fit-in/200x200/avatars/123/abc.png

        Transformation parameters:
        - width: Desired width in pixels
        - height: Desired height in pixels
        - fit: Fit mode ('cover', 'contain', 'fill', 'inside', 'outside')

        Without IMAGE_TRANSFORM_URL, returns the original image URL.
        """
        # Check if dynamic image transformation is configured
        transform_url = getattr(settings, "IMAGE_TRANSFORM_URL", None)

        if transform_url and (width or height):
            # Build transformation path (Thumbor-compatible format)
            # Format: /fit-in/WIDTHxHEIGHT/key or /WIDTHxHEIGHT/key
            w = width or 0
            h = height or 0
            size_spec = f"{w}x{h}"

            if fit:
                # Thumbor-style fit modes: fit-in, adaptive-fit-in, etc.
                return f"{transform_url.rstrip('/')}/{fit}/{size_spec}/{key}"
            else:
                return f"{transform_url.rstrip('/')}/{size_spec}/{key}"

        # Return original URL (no transformation)
        if self.use_s3:
            custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
            if custom_domain:
                return f"https://{custom_domain}/{key}"
            return f"https://{self.bucket_name}.s3.amazonaws.com/{key}"
        else:
            # Local development: return absolute URL to backend
            backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")
            return f"{backend_url}{settings.MEDIA_URL}{key}"


# Singleton instance
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
