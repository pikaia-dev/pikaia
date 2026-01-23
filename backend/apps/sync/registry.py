"""
Sync entity registry.

Maps entity types to their model classes and conflict resolution strategies.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from apps.sync.exceptions import UnknownEntityTypeError

if TYPE_CHECKING:
    from apps.sync.models import SyncableModel


class SyncRegistry:
    """
    Registry of syncable entity types and their configurations.

    Provides centralized mapping of entity type strings to model classes
    and their associated services.
    """

    _entities: dict[str, type[SyncableModel]] = {}
    _services: dict[str, Any] = {}
    _serializers: dict[str, Callable[[SyncableModel], dict]] = {}

    @classmethod
    def register(
        cls,
        entity_type: str,
        model: type[SyncableModel],
        service: Any | None = None,
        serializer: Callable[[SyncableModel], dict] | None = None,
    ) -> None:
        """
        Register a syncable entity type.

        Args:
            entity_type: String identifier (e.g., 'contact', 'time_entry')
            model: The Django model class
            service: Optional service class for business logic
            serializer: Optional function to serialize entity to dict
        """
        cls._entities[entity_type] = model
        if service is not None:
            cls._services[entity_type] = service
        if serializer is not None:
            cls._serializers[entity_type] = serializer

    @classmethod
    def get_model(cls, entity_type: str) -> type[SyncableModel]:
        """
        Get the model class for an entity type.

        Args:
            entity_type: The entity type string

        Returns:
            The model class

        Raises:
            UnknownEntityTypeError: If entity type is not registered
        """
        if entity_type not in cls._entities:
            raise UnknownEntityTypeError(f"Unknown entity type: {entity_type}")
        return cls._entities[entity_type]

    @classmethod
    def get_service(cls, entity_type: str) -> Any | None:
        """Get the service class for an entity type, if registered."""
        return cls._services.get(entity_type)

    @classmethod
    def get_serializer(cls, entity_type: str) -> Callable[[SyncableModel], dict] | None:
        """Get the serializer function for an entity type, if registered."""
        return cls._serializers.get(entity_type)

    @classmethod
    def get_all_entity_types(cls) -> list[str]:
        """Get list of all registered entity types."""
        return list(cls._entities.keys())

    @classmethod
    def get_all_models(cls) -> list[type[SyncableModel]]:
        """Get list of all registered model classes."""
        return list(cls._entities.values())

    @classmethod
    def get_lww_models(cls) -> list[type[SyncableModel]]:
        """Get models that use field-level LWW (have field_timestamps)."""
        from apps.sync.models import FieldLevelLWWMixin

        return [m for m in cls._entities.values() if issubclass(m, FieldLevelLWWMixin)]

    @classmethod
    def is_registered(cls, entity_type: str) -> bool:
        """Check if an entity type is registered."""
        return entity_type in cls._entities

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations. Useful for testing."""
        cls._entities.clear()
        cls._services.clear()
        cls._serializers.clear()
