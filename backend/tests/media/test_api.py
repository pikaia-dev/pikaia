"""
Tests for media upload API endpoints.
"""

import uuid
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory
from ninja.errors import HttpError
from PIL import Image

from apps.media.api import confirm_upload, delete_image, request_upload
from apps.media.models import UploadedImage
from apps.media.schemas import ConfirmUploadSchema, UploadRequestSchema
from apps.media.services import StorageService
from tests.accounts.factories import MemberFactory, OrganizationFactory, UserFactory


def create_test_image_bytes(width: int = 100, height: int = 100) -> bytes:
    """Create a test image as bytes."""
    img = Image.new("RGB", (width, height), color="red")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def storage_service() -> StorageService:
    """Storage service for media uploads (module-specific)."""
    return StorageService()


@pytest.mark.django_db
class TestUploadRequest:
    """Tests for the upload request endpoint."""

    def test_request_avatar_upload(self, request_factory: RequestFactory) -> None:
        """Should return upload URL for avatar."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.post("/api/v1/media/upload-request")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UploadRequestSchema(
            filename="avatar.png",
            content_type="image/png",
            size_bytes=50000,
            image_type="avatar",
        )

        result = request_upload(request, payload)

        assert result.upload_url
        assert result.key.startswith("avatars/")
        assert str(user.id) in result.key
        assert result.method in ("PUT", "POST")

    def test_request_logo_upload(self, request_factory: RequestFactory) -> None:
        """Should return upload URL for logo."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.post("/api/v1/media/upload-request")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UploadRequestSchema(
            filename="logo.jpg",
            content_type="image/jpeg",
            size_bytes=100000,
            image_type="logo",
        )

        result = request_upload(request, payload)

        assert result.upload_url
        assert result.key.startswith("logos/")
        assert str(org.id) in result.key

    def test_rejects_invalid_content_type(self, request_factory: RequestFactory) -> None:
        """Should reject non-image content types."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.post("/api/v1/media/upload-request")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UploadRequestSchema(
            filename="document.pdf",
            content_type="application/pdf",
            size_bytes=50000,
            image_type="avatar",
        )

        with pytest.raises(HttpError) as exc_info:
            request_upload(request, payload)

        assert exc_info.value.status_code == 400
        assert "content type" in str(exc_info.value.message).lower()

    def test_rejects_oversized_avatar(self, request_factory: RequestFactory) -> None:
        """Should reject avatars larger than 10MB."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.post("/api/v1/media/upload-request")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = UploadRequestSchema(
            filename="big_avatar.png",
            content_type="image/png",
            size_bytes=15 * 1024 * 1024,  # 15MB - too large
            image_type="avatar",
        )

        with pytest.raises(HttpError) as exc_info:
            request_upload(request, payload)

        assert exc_info.value.status_code == 400
        assert "too large" in str(exc_info.value.message).lower()

    def test_unauthenticated_request(self, request_factory: RequestFactory) -> None:
        """Should reject unauthenticated requests."""
        request = request_factory.post("/api/v1/media/upload-request")

        payload = UploadRequestSchema(
            filename="avatar.png",
            content_type="image/png",
            size_bytes=50000,
            image_type="avatar",
        )

        with pytest.raises(HttpError) as exc_info:
            request_upload(request, payload)

        assert exc_info.value.status_code == 401


@pytest.mark.django_db
class TestConfirmUpload:
    """Tests for the confirm upload endpoint."""

    def test_confirm_avatar_upload(self, request_factory: RequestFactory) -> None:
        """Should confirm upload and update user avatar_url."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.post("/api/v1/media/confirm")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        key = f"avatars/{user.id}/test123.png"
        payload = ConfirmUploadSchema(key=key, image_type="avatar")

        # Mock storage service
        with patch("apps.media.api.get_storage_service") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.confirm_upload.return_value = MagicMock(
                content_type="image/png",
                size_bytes=50000,
                width=200,
                height=200,
            )
            mock_storage.get_public_url.return_value = f"/media/{key}"
            mock_get_storage.return_value = mock_storage

            result = confirm_upload(request, payload)

        assert result.url == f"/media/{key}"
        assert result.width == 200
        assert result.height == 200

        # Check database record created
        assert UploadedImage.objects.filter(storage_key=key).exists()

        # Check user avatar_url updated
        user.refresh_from_db()
        assert user.avatar_url == f"/media/{key}"

    def test_confirm_missing_file(self, request_factory: RequestFactory) -> None:
        """Should return 404 when file not found."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.post("/api/v1/media/confirm")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        payload = ConfirmUploadSchema(key="nonexistent/file.png", image_type="avatar")

        with patch("apps.media.api.get_storage_service") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.confirm_upload.return_value = None
            mock_get_storage.return_value = mock_storage

            with pytest.raises(HttpError) as exc_info:
                confirm_upload(request, payload)

        assert exc_info.value.status_code == 404


@pytest.mark.django_db
class TestDeleteImage:
    """Tests for the delete image endpoint."""

    def test_user_can_delete_own_avatar(self, request_factory: RequestFactory) -> None:
        """User should be able to delete their own avatar."""
        org = OrganizationFactory()
        user = UserFactory(avatar_url="/media/avatars/1/test.png")
        member = MemberFactory(user=user, organization=org)

        image = UploadedImage.objects.create(
            storage_key="avatars/1/test.png",
            image_type="avatar",
            content_type="image/png",
            size_bytes=50000,
            user=user,
            uploaded_by=user,
        )

        request = request_factory.delete(f"/api/v1/media/{image.id}")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        with patch("apps.media.api.get_storage_service") as mock_get_storage:
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage

            result = delete_image(request, str(image.id))

        assert result["message"] == "Image deleted successfully"
        assert not UploadedImage.objects.filter(id=image.id).exists()

        # Check avatar_url cleared
        user.refresh_from_db()
        assert user.avatar_url == ""

    def test_user_cannot_delete_others_avatar(self, request_factory: RequestFactory) -> None:
        """User should not be able to delete another user's avatar."""
        org = OrganizationFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        member = MemberFactory(user=user1, organization=org)

        image = UploadedImage.objects.create(
            storage_key="avatars/2/test.png",
            image_type="avatar",
            content_type="image/png",
            size_bytes=50000,
            user=user2,
            uploaded_by=user2,
        )

        request = request_factory.delete(f"/api/v1/media/{image.id}")
        request.auth_user = user1  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        with pytest.raises(HttpError) as exc_info:
            delete_image(request, str(image.id))

        assert exc_info.value.status_code == 403

    def test_admin_can_delete_org_logo(self, request_factory: RequestFactory) -> None:
        """Admin should be able to delete organization logo."""
        org = OrganizationFactory(logo_url="/media/logos/1/test.png")
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="admin")

        image = UploadedImage.objects.create(
            storage_key="logos/1/test.png",
            image_type="logo",
            content_type="image/png",
            size_bytes=100000,
            organization=org,
            uploaded_by=user,
        )

        request = request_factory.delete(f"/api/v1/media/{image.id}")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        with patch("apps.media.api.get_storage_service") as mock_get_storage:
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage

            result = delete_image(request, str(image.id))

        assert result["message"] == "Image deleted successfully"
        assert not UploadedImage.objects.filter(id=image.id).exists()

    def test_delete_nonexistent_image(self, request_factory: RequestFactory) -> None:
        """Should return 404 for nonexistent image."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.delete(f"/api/v1/media/{uuid.uuid4()}")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        with pytest.raises(HttpError) as exc_info:
            delete_image(request, str(uuid.uuid4()))

        assert exc_info.value.status_code == 404


@pytest.mark.django_db
class TestLogoStytchSync:
    """Tests for syncing organization logos to Stytch."""

    def test_confirm_logo_upload_syncs_to_stytch(self, request_factory: RequestFactory) -> None:
        """Should sync logo URL to Stytch after confirming logo upload."""
        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.post("/api/v1/media/confirm")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        key = f"logos/{org.id}/logo123.png"
        payload = ConfirmUploadSchema(key=key, image_type="logo")

        with (
            patch("apps.media.api.get_storage_service") as mock_get_storage,
            patch("apps.accounts.stytch_client.get_stytch_client") as mock_stytch,
        ):
            mock_storage = MagicMock()
            mock_storage.confirm_upload.return_value = MagicMock(
                content_type="image/png",
                size_bytes=100000,
                width=400,
                height=400,
            )
            mock_storage.get_public_url.return_value = f"/media/{key}"
            mock_get_storage.return_value = mock_storage

            mock_client = MagicMock()
            mock_stytch.return_value = mock_client

            confirm_upload(request, payload)

        # Verify Stytch was called with the logo URL
        mock_client.organizations.update.assert_called_once_with(
            organization_id=org.stytch_org_id,
            organization_logo_url=f"/media/{key}",
        )

    def test_delete_logo_syncs_to_stytch(self, request_factory: RequestFactory) -> None:
        """Should sync empty logo URL to Stytch after deleting logo."""
        org = OrganizationFactory(logo_url="/media/logos/1/test.png")
        user = UserFactory()
        member = MemberFactory(user=user, organization=org, role="admin")

        image = UploadedImage.objects.create(
            storage_key="logos/1/test.png",
            image_type="logo",
            content_type="image/png",
            size_bytes=100000,
            organization=org,
            uploaded_by=user,
        )

        request = request_factory.delete(f"/api/v1/media/{image.id}")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        with (
            patch("apps.media.api.get_storage_service") as mock_get_storage,
            patch("apps.accounts.stytch_client.get_stytch_client") as mock_stytch,
        ):
            mock_storage = MagicMock()
            mock_get_storage.return_value = mock_storage

            mock_client = MagicMock()
            mock_stytch.return_value = mock_client

            delete_image(request, str(image.id))

        # Verify Stytch was called with empty logo URL
        mock_client.organizations.update.assert_called_once_with(
            organization_id=org.stytch_org_id,
            organization_logo_url="",
        )

    def test_stytch_sync_failure_does_not_break_upload(
        self, request_factory: RequestFactory
    ) -> None:
        """Logo upload should succeed even if Stytch sync fails."""
        from stytch.core.response_base import StytchError

        org = OrganizationFactory()
        user = UserFactory()
        member = MemberFactory(user=user, organization=org)

        request = request_factory.post("/api/v1/media/confirm")
        request.auth_user = user  # type: ignore[attr-defined]
        request.auth_member = member  # type: ignore[attr-defined]
        request.auth_organization = org  # type: ignore[attr-defined]

        key = f"logos/{org.id}/logo123.png"
        payload = ConfirmUploadSchema(key=key, image_type="logo")

        with (
            patch("apps.media.api.get_storage_service") as mock_get_storage,
            patch("apps.accounts.stytch_client.get_stytch_client") as mock_stytch,
        ):
            mock_storage = MagicMock()
            mock_storage.confirm_upload.return_value = MagicMock(
                content_type="image/png",
                size_bytes=100000,
                width=400,
                height=400,
            )
            mock_storage.get_public_url.return_value = f"/media/{key}"
            mock_get_storage.return_value = mock_storage

            # Simulate Stytch API failure
            mock_client = MagicMock()
            mock_error = MagicMock()
            mock_error.error_message = "API temporarily unavailable"
            mock_client.organizations.update.side_effect = StytchError(mock_error)
            mock_stytch.return_value = mock_client

            # Should not raise - graceful degradation
            result = confirm_upload(request, payload)

        # Upload should still succeed
        assert result.url == f"/media/{key}"
        assert UploadedImage.objects.filter(storage_key=key).exists()

        # Org logo_url should be updated locally
        org.refresh_from_db()
        assert org.logo_url == f"/media/{key}"


@pytest.mark.django_db
class TestStorageService:
    """Tests for the storage service."""

    def test_validate_upload_request_valid(self, storage_service: StorageService) -> None:
        """Should return no errors for valid request."""
        errors = storage_service.validate_upload_request(
            content_type="image/png",
            size_bytes=100000,
            image_type="avatar",
        )
        assert errors == []

    def test_validate_upload_request_invalid_type(self, storage_service: StorageService) -> None:
        """Should reject invalid content type."""
        errors = storage_service.validate_upload_request(
            content_type="application/pdf",
            size_bytes=100000,
            image_type="avatar",
        )
        assert len(errors) == 1
        assert "content type" in errors[0].lower()

    def test_validate_upload_request_oversized(self, storage_service: StorageService) -> None:
        """Should reject oversized files."""
        errors = storage_service.validate_upload_request(
            content_type="image/png",
            size_bytes=15 * 1024 * 1024,  # 15MB - exceeds 10MB limit
            image_type="avatar",
        )
        assert len(errors) == 1
        assert "too large" in errors[0].lower()

    def test_generate_key(self, storage_service: StorageService) -> None:
        """Should generate unique keys with correct structure."""
        key1 = storage_service.generate_key(
            image_type="avatar",
            owner_id="123",
            filename="test.png",
        )
        key2 = storage_service.generate_key(
            image_type="avatar",
            owner_id="123",
            filename="test.png",
        )

        assert key1.startswith("avatars/123/")
        assert key1.endswith(".png")
        # Keys should be unique
        assert key1 != key2
