"""
Pytest fixtures for sync tests.

Provides test model and registry setup.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from django.db import models

from apps.sync.models import FieldLevelLWWMixin, SyncableModel
from apps.sync.registry import SyncRegistry

if TYPE_CHECKING:
    from apps.accounts.models import Member
    from apps.organizations.models import Organization


class SyncTestContact(FieldLevelLWWMixin, SyncableModel):
    """
    Test-only syncable model for sync engine tests.

    This model is created dynamically in the test database.
    Uses UUID primary keys like all SyncableModel subclasses.
    """

    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        app_label = "sync"
        # Don't use the abstract indexes - define explicitly for test model
        indexes = []


def serialize_test_contact(contact: SyncTestContact) -> dict:
    """Serializer for test contact."""
    return {
        "id": str(contact.id),  # Convert UUID to string for JSON serialization
        "name": contact.name,
        "email": contact.email,
        "phone": contact.phone,
        "notes": contact.notes,
        "sync_version": contact.sync_version,
        "created_at": contact.created_at.isoformat(),
        "updated_at": contact.updated_at.isoformat(),
        "field_timestamps": contact.field_timestamps,
    }


@pytest.fixture
def sync_registry():
    """
    Set up and tear down the sync registry for tests.

    Registers SyncTestContact and cleans up after test.
    """
    # Clear any existing registrations
    SyncRegistry.clear()

    # Register test model
    SyncRegistry.register(
        entity_type="test_contact",
        model=SyncTestContact,
        serializer=serialize_test_contact,
    )

    yield SyncRegistry

    # Clean up
    SyncRegistry.clear()


@pytest.fixture
def test_contact_factory(db):
    """Factory function for creating test contacts."""
    from uuid import UUID

    def create(
        organization: Organization,
        member: Member | None = None,
        name: str = "Test Contact",
        email: str = "",
        phone: str = "",
        notes: str = "",
        entity_id: UUID | None = None,
        field_timestamps: dict | None = None,
        deleted_at: datetime | None = None,
    ) -> SyncTestContact:
        contact = SyncTestContact(
            organization=organization,
            last_modified_by=member,
            name=name,
            email=email,
            phone=phone,
            notes=notes,
        )
        if entity_id:
            contact.id = entity_id
        if field_timestamps:
            contact.field_timestamps = field_timestamps
        contact.save()

        if deleted_at:
            contact.deleted_at = deleted_at
            contact.save(update_fields=["deleted_at"])

        return contact

    return create
