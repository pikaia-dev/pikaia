"""Sync-specific exceptions."""


class SyncError(Exception):
    """Base exception for sync errors."""

    pass


class UnknownEntityTypeError(SyncError):
    """Raised when entity type is not registered."""

    pass


class EntityNotFoundError(SyncError):
    """Raised when entity does not exist."""

    pass


class CursorInvalidError(SyncError):
    """Raised when cursor cannot be decoded or is malformed."""

    pass


class ConflictError(SyncError):
    """Raised when there's a conflict that requires client action."""

    def __init__(self, message: str, conflict_data: dict | None = None):
        super().__init__(message)
        self.conflict_data = conflict_data or {}
