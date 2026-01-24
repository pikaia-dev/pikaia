"""
Tests for field-level LWW conflict resolution.
"""

from datetime import UTC, datetime

import pytest

from apps.sync.services import apply_field_level_lww
from tests.accounts.factories import OrganizationFactory


@pytest.mark.django_db
class TestFieldLevelLWW:
    """Tests for apply_field_level_lww function."""

    def test_client_wins_when_newer(self, sync_registry, test_contact_factory):
        """Client should win when its timestamp is newer than server's."""
        org = OrganizationFactory.create()

        # Server has old data
        server_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        contact = test_contact_factory(
            organization=org,
            name="Old Name",
            field_timestamps={"name": server_ts.isoformat()},
        )

        # Client has newer timestamp
        client_ts = datetime(2025, 1, 23, 11, 0, 0, tzinfo=UTC)
        client_data = {"name": "New Name"}

        applied, rejected = apply_field_level_lww(contact, client_data, client_ts)

        assert applied == {"name": "New Name"}
        assert rejected == {}
        assert contact.name == "New Name"
        assert contact.get_field_timestamp("name") == client_ts

    def test_server_wins_when_newer(self, sync_registry, test_contact_factory):
        """Server should win when its timestamp is newer than client's."""
        org = OrganizationFactory.create()

        # Server has newer data
        server_ts = datetime(2025, 1, 23, 12, 0, 0, tzinfo=UTC)
        contact = test_contact_factory(
            organization=org,
            name="Server Name",
            field_timestamps={"name": server_ts.isoformat()},
        )

        # Client has older timestamp
        client_ts = datetime(2025, 1, 23, 11, 0, 0, tzinfo=UTC)
        client_data = {"name": "Client Name"}

        applied, rejected = apply_field_level_lww(contact, client_data, client_ts)

        assert applied == {}
        assert "name" in rejected
        assert rejected["name"]["client_value"] == "Client Name"
        assert rejected["name"]["server_value"] == "Server Name"
        assert contact.name == "Server Name"  # Unchanged

    def test_client_wins_when_server_has_no_timestamp(self, sync_registry, test_contact_factory):
        """Client should win when server has no timestamp (new field or migration)."""
        org = OrganizationFactory.create()

        # Server has no timestamp for this field
        contact = test_contact_factory(
            organization=org,
            name="Original",
            field_timestamps={},  # No timestamps
        )

        client_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        client_data = {"name": "Updated"}

        applied, rejected = apply_field_level_lww(contact, client_data, client_ts)

        assert applied == {"name": "Updated"}
        assert rejected == {}
        assert contact.name == "Updated"

    def test_multiple_fields_resolved_independently(self, sync_registry, test_contact_factory):
        """Each field should be resolved independently."""
        org = OrganizationFactory.create()

        # Server has different timestamps for different fields
        old_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        new_ts = datetime(2025, 1, 23, 12, 0, 0, tzinfo=UTC)

        contact = test_contact_factory(
            organization=org,
            name="Server Name",
            phone="Server Phone",
            field_timestamps={
                "name": old_ts.isoformat(),  # Old - client should win
                "phone": new_ts.isoformat(),  # New - server should win
            },
        )

        # Client timestamp is in between
        client_ts = datetime(2025, 1, 23, 11, 0, 0, tzinfo=UTC)
        client_data = {"name": "Client Name", "phone": "Client Phone"}

        applied, rejected = apply_field_level_lww(contact, client_data, client_ts)

        assert applied == {"name": "Client Name"}  # Client wins (newer than server)
        assert "phone" in rejected  # Server wins (newer than client)
        assert contact.name == "Client Name"
        assert contact.phone == "Server Phone"

    def test_same_value_not_reported_as_conflict(self, sync_registry, test_contact_factory):
        """Should not report conflict when values are the same."""
        org = OrganizationFactory.create()

        server_ts = datetime(2025, 1, 23, 12, 0, 0, tzinfo=UTC)
        contact = test_contact_factory(
            organization=org,
            name="Same Name",
            field_timestamps={"name": server_ts.isoformat()},
        )

        # Client has older timestamp but same value
        client_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        client_data = {"name": "Same Name"}

        applied, rejected = apply_field_level_lww(contact, client_data, client_ts)

        # No conflict because values are the same
        assert applied == {}
        assert rejected == {}

    def test_excluded_fields_are_skipped(self, sync_registry, test_contact_factory):
        """Should skip fields in LWW_EXCLUDED_FIELDS."""
        org = OrganizationFactory.create()

        contact = test_contact_factory(
            organization=org,
            name="Test",
            field_timestamps={},
        )

        client_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        # Try to update excluded fields
        client_data = {
            "id": "should_not_change",
            "organization_id": 999,
            "sync_version": 999,
        }

        applied, rejected = apply_field_level_lww(contact, client_data, client_ts)

        assert applied == {}
        assert rejected == {}

    def test_nonexistent_fields_are_skipped(self, sync_registry, test_contact_factory):
        """Should skip fields that don't exist on the model."""
        org = OrganizationFactory.create()

        contact = test_contact_factory(
            organization=org,
            name="Test",
            field_timestamps={},
        )

        client_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        client_data = {"nonexistent_field": "value"}

        applied, rejected = apply_field_level_lww(contact, client_data, client_ts)

        assert applied == {}
        assert rejected == {}

    def test_exact_same_timestamp_server_wins(self, sync_registry, test_contact_factory):
        """When timestamps are equal, server should win (tie-breaker)."""
        org = OrganizationFactory.create()

        same_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        contact = test_contact_factory(
            organization=org,
            name="Server Name",
            field_timestamps={"name": same_ts.isoformat()},
        )

        client_data = {"name": "Client Name"}

        applied, rejected = apply_field_level_lww(contact, client_data, same_ts)

        # Server wins on tie
        assert applied == {}
        assert "name" in rejected
        assert contact.name == "Server Name"

    def test_rejected_includes_timestamps(self, sync_registry, test_contact_factory):
        """Rejected fields should include both timestamps for debugging."""
        org = OrganizationFactory.create()

        server_ts = datetime(2025, 1, 23, 12, 0, 0, tzinfo=UTC)
        contact = test_contact_factory(
            organization=org,
            name="Server",
            field_timestamps={"name": server_ts.isoformat()},
        )

        client_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        client_data = {"name": "Client"}

        applied, rejected = apply_field_level_lww(contact, client_data, client_ts)

        assert "name" in rejected
        assert "client_timestamp" in rejected["name"]
        assert "server_timestamp" in rejected["name"]
        assert rejected["name"]["client_timestamp"] == client_ts.isoformat()
        assert rejected["name"]["server_timestamp"] == server_ts.isoformat()


@pytest.mark.django_db
class TestConflictResolutionScenarios:
    """Real-world conflict resolution scenarios."""

    def test_concurrent_edit_different_fields(self, sync_registry, test_contact_factory):
        """
        Scenario: Two users edit different fields concurrently.
        Both changes should be merged.
        """
        org = OrganizationFactory.create()

        base_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        contact = test_contact_factory(
            organization=org,
            name="Original Name",
            phone="Original Phone",
            email="original@example.com",
            field_timestamps={
                "name": base_ts.isoformat(),
                "phone": base_ts.isoformat(),
                "email": base_ts.isoformat(),
            },
        )

        # User A edits name at 10:05
        user_a_ts = datetime(2025, 1, 23, 10, 5, 0, tzinfo=UTC)
        user_a_data = {"name": "Name from User A"}
        applied_a, rejected_a = apply_field_level_lww(contact, user_a_data, user_a_ts)

        assert applied_a == {"name": "Name from User A"}
        assert rejected_a == {}

        # User B edits phone at 10:10 (after A's change)
        user_b_ts = datetime(2025, 1, 23, 10, 10, 0, tzinfo=UTC)
        user_b_data = {"phone": "Phone from User B"}
        applied_b, rejected_b = apply_field_level_lww(contact, user_b_data, user_b_ts)

        assert applied_b == {"phone": "Phone from User B"}
        assert rejected_b == {}

        # Final state has both changes
        assert contact.name == "Name from User A"
        assert contact.phone == "Phone from User B"
        assert contact.email == "original@example.com"

    def test_concurrent_edit_same_field_last_wins(self, sync_registry, test_contact_factory):
        """
        Scenario: Two users edit the same field concurrently.
        The later edit should win.
        """
        org = OrganizationFactory.create()

        base_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        contact = test_contact_factory(
            organization=org,
            name="Original",
            field_timestamps={"name": base_ts.isoformat()},
        )

        # User A edits at 10:05
        user_a_ts = datetime(2025, 1, 23, 10, 5, 0, tzinfo=UTC)
        apply_field_level_lww(contact, {"name": "Name A"}, user_a_ts)
        contact.save()

        assert contact.name == "Name A"

        # User B edits at 10:10 (later)
        user_b_ts = datetime(2025, 1, 23, 10, 10, 0, tzinfo=UTC)
        apply_field_level_lww(contact, {"name": "Name B"}, user_b_ts)
        contact.save()

        assert contact.name == "Name B"

        # User A's stale edit at 10:03 arrives late (rejected)
        stale_ts = datetime(2025, 1, 23, 10, 3, 0, tzinfo=UTC)
        applied, rejected = apply_field_level_lww(contact, {"name": "Stale A"}, stale_ts)

        assert applied == {}
        assert "name" in rejected
        assert contact.name == "Name B"  # Unchanged

    def test_offline_edits_merge_on_sync(self, sync_registry, test_contact_factory):
        """
        Scenario: User edits offline, server has been updated by someone else.
        Non-conflicting edits should merge.
        """
        org = OrganizationFactory.create()

        # Initial state at 10:00
        base_ts = datetime(2025, 1, 23, 10, 0, 0, tzinfo=UTC)
        contact = test_contact_factory(
            organization=org,
            name="Original Name",
            email="original@example.com",
            phone="555-0000",
            field_timestamps={
                "name": base_ts.isoformat(),
                "email": base_ts.isoformat(),
                "phone": base_ts.isoformat(),
            },
        )

        # Server gets updated at 10:30 (admin changes email)
        server_update_ts = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        contact.email = "admin@example.com"
        contact.set_field_timestamp("email", server_update_ts)
        contact.save()

        # Offline user made changes at 10:15 and syncs at 11:00
        # They changed name and phone (not email)
        offline_ts = datetime(2025, 1, 23, 10, 15, 0, tzinfo=UTC)
        offline_data = {
            "name": "Offline Name",
            "phone": "555-1111",
            "email": "offline@example.com",  # Also tried to change email
        }

        applied, rejected = apply_field_level_lww(contact, offline_data, offline_ts)

        # Name and phone win (no server change since user's edit)
        assert "name" in applied
        assert "phone" in applied

        # Email rejected (server's update at 10:30 is newer than user's at 10:15)
        assert "email" in rejected

        assert contact.name == "Offline Name"
        assert contact.phone == "555-1111"
        assert contact.email == "admin@example.com"  # Server's version kept
