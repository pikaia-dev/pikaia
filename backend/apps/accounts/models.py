"""
Accounts models - user and membership management.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    """Custom manager for User model."""

    def create_user(
        self,
        email: str,
        **extra_fields,
    ) -> "User":
        """Create and return a regular user."""
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user: User = self.model(email=email, **extra_fields)  # type: ignore[assignment]
        # No password - Stytch handles authentication
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        **extra_fields,
    ) -> "User":
        """Create and return a superuser (for Django admin access)."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model - cross-org identity.

    This is AUTH_USER_MODEL. Stytch handles authentication;
    we sync user data for Django ecosystem compatibility.
    Email is the cross-org identifier in Stytch B2B.
    """

    # User info - email is the cross-org identifier
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(
        blank=True,
        default="",
        help_text="URL to user's avatar image",
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Phone number in E.164 format (e.g., +14155551234)",
    )
    phone_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when phone was verified via OTP. NULL = unverified.",
    )

    # Django auth compatibility
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False,
        help_text="Can access Django admin",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Email is already required via USERNAME_FIELD

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email


class MemberManager(models.Manager):
    """Custom manager for Member model that excludes soft-deleted members."""

    def get_queryset(self) -> models.QuerySet:
        """Return only active (non-deleted) members by default."""
        return super().get_queryset().filter(deleted_at__isnull=True)


class MemberAllManager(models.Manager):
    """Manager that includes all members, including soft-deleted ones."""

    pass


class Member(models.Model):
    """
    Org-scoped membership linking User to Organization.

    A user can be a member of multiple organizations with different roles.
    Role is synced from Stytch RBAC.
    """

    # Stytch sync
    stytch_member_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Stytch member_id, e.g. 'member-xxx'",
    )

    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="members",
    )

    # Role synced from Stytch (admin, member, viewer)
    role = models.CharField(
        max_length=50,
        default="member",
        db_index=True,
        help_text="Org-level role from Stytch RBAC",
    )

    # Soft delete
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Soft delete timestamp. NULL = active member.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Managers
    objects = MemberManager()
    all_objects = MemberAllManager()

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["user", "organization"]
        indexes = [
            models.Index(fields=["organization", "deleted_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} @ {self.organization.name} ({self.role})"

    @property
    def is_admin(self) -> bool:
        """Check if member has admin role."""
        return self.role == "admin"

    @property
    def is_deleted(self) -> bool:
        """Check if member is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this member by setting deleted_at timestamp."""
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])
