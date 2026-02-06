"""
Media models for tracking uploaded images.
"""

import uuid

from django.db import models


class UploadedImage(models.Model):
    """
    Tracks uploaded images with metadata.

    Used for user avatars, organization logos, and other images.
    The actual file is stored in S3 (production) or local filesystem (development).
    """

    class ImageType(models.TextChoices):
        AVATAR = "avatar", "Avatar"
        LOGO = "logo", "Logo"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storage_key = models.CharField(
        max_length=500,
        unique=True,
        help_text="S3 key or local path to the file",
    )
    image_type = models.CharField(max_length=20, choices=ImageType.choices)
    content_type = models.CharField(max_length=100, help_text="MIME type of the image")
    size_bytes = models.PositiveIntegerField(help_text="File size in bytes")
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    # Ownership - only one of these should be set
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="uploaded_images",
        help_text="User who owns this image (for avatars)",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="uploaded_images",
        help_text="Organization that owns this image (for logos)",
    )

    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        help_text="User who uploaded this image",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "image_type"]),
            models.Index(fields=["organization", "image_type"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, organization__isnull=True)
                    | models.Q(user__isnull=True, organization__isnull=False)
                ),
                name="uploaded_image_single_owner",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.image_type}: {self.storage_key}"
