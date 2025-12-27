"""
Core models - shared base classes and utilities.
"""

from django.db import models


class TimestampedModel(models.Model):
    """
    Abstract base model with created_at/updated_at timestamps.
    
    All business entities should inherit from this or TenantScopedModel.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimestampedModel):
    """
    Abstract base model for all organization-scoped entities.
    
    Provides:
    - Automatic organization FK
    - Timestamps from TimestampedModel
    
    Usage:
        class Project(TenantScopedModel):
            name = models.CharField(max_length=255)
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
    )

    class Meta:
        abstract = True
