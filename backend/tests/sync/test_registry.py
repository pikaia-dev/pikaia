"""
Tests for sync registry.
"""

import pytest

from apps.sync.exceptions import UnknownEntityTypeError
from apps.sync.registry import SyncRegistry
from tests.sync.conftest import SyncTestContact


class TestSyncRegistry:
    """Tests for SyncRegistry class."""

    def setup_method(self):
        """Clear registry before each test."""
        SyncRegistry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        SyncRegistry.clear()

    def test_register_entity(self):
        """Should register entity type with model."""
        SyncRegistry.register(
            entity_type="test_contact",
            model=SyncTestContact,
        )

        assert SyncRegistry.is_registered("test_contact")
        assert SyncRegistry.get_model("test_contact") == SyncTestContact

    def test_register_with_service(self):
        """Should register entity with optional service."""

        class MockService:
            pass

        SyncRegistry.register(
            entity_type="test_contact",
            model=SyncTestContact,
            service=MockService,
        )

        assert SyncRegistry.get_service("test_contact") == MockService

    def test_register_with_serializer(self):
        """Should register entity with optional serializer."""

        def mock_serializer(entity):
            return {"id": entity.id}

        SyncRegistry.register(
            entity_type="test_contact",
            model=SyncTestContact,
            serializer=mock_serializer,
        )

        assert SyncRegistry.get_serializer("test_contact") == mock_serializer

    def test_get_model_unknown_type_raises(self):
        """Should raise UnknownEntityTypeError for unknown type."""
        with pytest.raises(UnknownEntityTypeError):
            SyncRegistry.get_model("nonexistent")

    def test_get_service_returns_none_if_not_registered(self):
        """Should return None if service not registered."""
        SyncRegistry.register(
            entity_type="test_contact",
            model=SyncTestContact,
        )

        assert SyncRegistry.get_service("test_contact") is None

    def test_get_serializer_returns_none_if_not_registered(self):
        """Should return None if serializer not registered."""
        SyncRegistry.register(
            entity_type="test_contact",
            model=SyncTestContact,
        )

        assert SyncRegistry.get_serializer("test_contact") is None

    def test_is_registered_false_for_unknown(self):
        """Should return False for unregistered types."""
        assert not SyncRegistry.is_registered("nonexistent")

    def test_get_all_entity_types(self):
        """Should return list of all registered types."""
        SyncRegistry.register("type_a", SyncTestContact)
        SyncRegistry.register("type_b", SyncTestContact)

        types = SyncRegistry.get_all_entity_types()

        assert "type_a" in types
        assert "type_b" in types
        assert len(types) == 2

    def test_get_all_models(self):
        """Should return list of all registered models."""
        SyncRegistry.register("type_a", SyncTestContact)

        models = SyncRegistry.get_all_models()

        assert SyncTestContact in models

    def test_get_lww_models(self):
        """Should return only models using field-level LWW."""
        from apps.sync.models import FieldLevelLWWMixin

        SyncRegistry.register("test_contact", SyncTestContact)

        lww_models = SyncRegistry.get_lww_models()

        # SyncTestContact has FieldLevelLWWMixin
        assert SyncTestContact in lww_models
        for model in lww_models:
            assert issubclass(model, FieldLevelLWWMixin)

    def test_clear_removes_all_registrations(self):
        """Should remove all registrations."""
        SyncRegistry.register("type_a", SyncTestContact)
        SyncRegistry.register("type_b", SyncTestContact)

        SyncRegistry.clear()

        assert not SyncRegistry.is_registered("type_a")
        assert not SyncRegistry.is_registered("type_b")
        assert len(SyncRegistry.get_all_entity_types()) == 0

    def test_register_overwrites_existing(self):
        """Should overwrite existing registration."""

        class MockService1:
            pass

        class MockService2:
            pass

        SyncRegistry.register("test", SyncTestContact, service=MockService1)
        SyncRegistry.register("test", SyncTestContact, service=MockService2)

        assert SyncRegistry.get_service("test") == MockService2
