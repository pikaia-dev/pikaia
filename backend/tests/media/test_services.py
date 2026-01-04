"""
Tests for media storage service.

Dedicated service layer tests (beyond API-level tests in test_api.py).
"""

from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import override_settings
from PIL import Image

from apps.media.services import ImageMetadata, StorageService, UploadInfo


def create_test_image_bytes(width: int = 100, height: int = 100, format: str = "PNG") -> bytes:
    """Create a test image as bytes."""
    img = Image.new("RGB", (width, height), color="red")
    buffer = BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


class TestStorageServiceInit:
    """Tests for StorageService initialization."""

    def test_initializes_without_s3(self) -> None:
        """Should initialize for local storage when USE_S3_STORAGE is False."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()
            assert service.use_s3 is False

    def test_initializes_with_s3(self) -> None:
        """Should initialize S3 client when USE_S3_STORAGE is True."""
        with patch("boto3.client") as mock_boto_client:
            with override_settings(
                USE_S3_STORAGE=True,
                AWS_ACCESS_KEY_ID="test-key",
                AWS_SECRET_ACCESS_KEY="test-secret",
                AWS_STORAGE_BUCKET_NAME="test-bucket",
                AWS_S3_REGION_NAME="us-west-2",
            ):
                service = StorageService()

                assert service.use_s3 is True
                mock_boto_client.assert_called_once_with(
                    "s3",
                    aws_access_key_id="test-key",
                    aws_secret_access_key="test-secret",
                    region_name="us-west-2",
                )


class TestGenerateKey:
    """Tests for key generation."""

    def test_generates_unique_keys(self) -> None:
        """Should generate unique keys for same input."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            key1 = service.generate_key("avatar", "user-123", "profile.png")
            key2 = service.generate_key("avatar", "user-123", "profile.png")

            assert key1 != key2

    def test_key_has_correct_prefix(self) -> None:
        """Should prefix key with pluralized image type."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            key = service.generate_key("avatar", "user-123", "photo.jpg")

            assert key.startswith("avatars/user-123/")

    def test_key_preserves_extension(self) -> None:
        """Should preserve original file extension."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            key = service.generate_key("logo", "org-456", "company.svg")

            assert key.endswith(".svg")

    def test_key_defaults_to_jpg_extension(self) -> None:
        """Should default to .jpg when no extension provided."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            key = service.generate_key("avatar", "user-123", "no-extension")

            assert key.endswith(".jpg")


class TestValidateUploadRequest:
    """Tests for upload validation (beyond API tests)."""

    def test_rejects_executable_mime_types(self) -> None:
        """Should reject potentially dangerous executable types."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            errors = service.validate_upload_request(
                content_type="application/x-executable",
                size_bytes=1000,
                image_type="avatar",
            )

            assert len(errors) >= 1
            assert any("content type" in e.lower() for e in errors)

    def test_allows_avif_format(self) -> None:
        """Should allow AVIF image format."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            errors = service.validate_upload_request(
                content_type="image/avif",
                size_bytes=500000,
                image_type="avatar",
            )

            assert errors == []


class TestGenerateUploadUrl:
    """Tests for upload URL generation."""

    def test_local_returns_post_method(self) -> None:
        """Should return POST method for local uploads."""
        with override_settings(USE_S3_STORAGE=False, BACKEND_URL="http://localhost:8000"):
            service = StorageService()

            result = service.generate_upload_url(
                key="avatars/123/test.png",
                content_type="image/png",
                size_bytes=50000,
            )

            assert isinstance(result, UploadInfo)
            assert result.method == "POST"
            assert result.upload_url == "http://localhost:8000/api/v1/media/direct-upload"
            assert result.key == "avatars/123/test.png"

    def test_s3_returns_put_method(self) -> None:
        """Should return PUT method with presigned URL for S3."""
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.aws.com/presigned"

        with patch("boto3.client", return_value=mock_s3):
            with override_settings(
                USE_S3_STORAGE=True,
                AWS_ACCESS_KEY_ID="key",
                AWS_SECRET_ACCESS_KEY="secret",
                AWS_STORAGE_BUCKET_NAME="bucket",
            ):
                service = StorageService()
                result = service.generate_upload_url(
                    key="avatars/123/test.png",
                    content_type="image/png",
                    size_bytes=50000,
                )

                assert result.method == "PUT"
                assert "presigned" in result.upload_url
                mock_s3.generate_presigned_url.assert_called_once()


class TestGetImageDimensions:
    """Tests for image dimension extraction."""

    def test_extracts_png_dimensions(self) -> None:
        """Should extract dimensions from PNG image."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()
            image_bytes = create_test_image_bytes(width=200, height=150)

            width, height = service._get_image_dimensions(image_bytes)

            assert width == 200
            assert height == 150

    def test_extracts_jpeg_dimensions(self) -> None:
        """Should extract dimensions from JPEG image."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()
            image_bytes = create_test_image_bytes(width=300, height=200, format="JPEG")

            width, height = service._get_image_dimensions(image_bytes)

            assert width == 300
            assert height == 200

    def test_returns_zero_for_invalid_data(self) -> None:
        """Should return (0, 0) for non-image data."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            width, height = service._get_image_dimensions(b"not an image")

            assert width == 0
            assert height == 0

    def test_returns_zero_for_empty_data(self) -> None:
        """Should return (0, 0) for empty data."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            width, height = service._get_image_dimensions(b"")

            assert width == 0
            assert height == 0


class TestGetImageUrl:
    """Tests for public URL generation."""

    def test_local_url_without_transform(self) -> None:
        """Should return local URL when no transform config."""
        with override_settings(
            USE_S3_STORAGE=False,
            BACKEND_URL="http://localhost:8000",
            MEDIA_URL="/media/",
        ):
            service = StorageService()

            url = service.get_image_url("avatars/123/test.png")

            assert url == "http://localhost:8000/media/avatars/123/test.png"

    def test_local_url_ignores_dimensions_without_transform(self) -> None:
        """Should ignore dimensions when IMAGE_TRANSFORM_URL not set."""
        with override_settings(
            USE_S3_STORAGE=False,
            BACKEND_URL="http://localhost:8000",
            MEDIA_URL="/media/",
            IMAGE_TRANSFORM_URL=None,
        ):
            service = StorageService()

            url = service.get_image_url("avatars/123/test.png", width=200, height=200)

            # Should return original URL without dimensions
            assert url == "http://localhost:8000/media/avatars/123/test.png"

    def test_transform_url_with_dimensions(self) -> None:
        """Should include dimensions when IMAGE_TRANSFORM_URL is set."""
        with override_settings(
            USE_S3_STORAGE=False,
            IMAGE_TRANSFORM_URL="https://transform.example.com",
        ):
            service = StorageService()

            url = service.get_image_url("avatars/123/test.png", width=200, height=150)

            assert url == "https://transform.example.com/200x150/avatars/123/test.png"

    def test_transform_url_with_fit_mode(self) -> None:
        """Should include fit mode in transform URL."""
        with override_settings(
            USE_S3_STORAGE=False,
            IMAGE_TRANSFORM_URL="https://transform.example.com",
        ):
            service = StorageService()

            url = service.get_image_url("avatars/123/test.png", width=200, height=200, fit="fit-in")

            assert url == "https://transform.example.com/fit-in/200x200/avatars/123/test.png"

    def test_s3_url_with_custom_domain(self) -> None:
        """Should use custom domain for S3 URLs when configured."""
        mock_s3 = MagicMock()

        with patch("boto3.client", return_value=mock_s3):
            with override_settings(
                USE_S3_STORAGE=True,
                AWS_ACCESS_KEY_ID="key",
                AWS_SECRET_ACCESS_KEY="secret",
                AWS_STORAGE_BUCKET_NAME="bucket",
                AWS_S3_CUSTOM_DOMAIN="cdn.example.com",
            ):
                service = StorageService()

                url = service.get_image_url("avatars/123/test.png")

                assert url == "https://cdn.example.com/avatars/123/test.png"


class TestSanitizeSVGInStorage:
    """Tests for SVG sanitization in storage."""

    def test_sanitizes_svg_and_reuploads(self) -> None:
        """Should sanitize SVG content and save back."""
        svg_content = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect onclick="alert('XSS')" x="10" y="10" width="50" height="50"/>
            <script>evil()</script>
        </svg>"""

        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            with (
                patch.object(service, "save_file") as mock_save,
                patch("apps.media.services.default_storage") as mock_storage,
            ):
                mock_storage.exists.return_value = True
                mock_file = MagicMock()
                mock_file.read.return_value = svg_content
                mock_storage.open.return_value.__enter__.return_value = mock_file

                result = service.sanitize_svg_in_storage("logos/123/logo.svg")

                assert result is not None
                assert b"<script" not in result
                assert b"onclick" not in result
                mock_save.assert_called_once()

    def test_returns_none_for_non_svg(self) -> None:
        """Should return None for non-SVG files."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            with patch("apps.media.services.default_storage") as mock_storage:
                mock_storage.exists.return_value = True
                mock_file = MagicMock()
                mock_file.read.return_value = create_test_image_bytes()
                mock_storage.open.return_value.__enter__.return_value = mock_file

                # mimetypes.guess_type will return 'image/png' for .png
                result = service.sanitize_svg_in_storage("avatars/123/photo.png")

                assert result is None


class TestConfirmUpload:
    """Tests for upload confirmation."""

    def test_returns_metadata_for_existing_file(self) -> None:
        """Should return ImageMetadata for existing file."""
        image_bytes = create_test_image_bytes(width=100, height=80)

        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            with patch("apps.media.services.default_storage") as mock_storage:
                mock_storage.exists.return_value = True
                mock_storage.size.return_value = len(image_bytes)
                mock_file = MagicMock()
                mock_file.read.return_value = image_bytes
                mock_storage.open.return_value.__enter__.return_value = mock_file

                result = service.confirm_upload("avatars/123/test.png")

                assert result is not None
                assert isinstance(result, ImageMetadata)
                assert result.width == 100
                assert result.height == 80
                assert result.size_bytes == len(image_bytes)

    def test_returns_none_for_missing_file(self) -> None:
        """Should return None when file doesn't exist."""
        with override_settings(USE_S3_STORAGE=False):
            service = StorageService()

            with patch("apps.media.services.default_storage") as mock_storage:
                mock_storage.exists.return_value = False

                result = service.confirm_upload("avatars/123/nonexistent.png")

                assert result is None
