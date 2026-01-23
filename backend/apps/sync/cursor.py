"""
Cursor encoding/decoding for sync pagination.

Cursors are opaque to clients but encode (timestamp, id) for efficient
database queries with stable ordering.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime

from apps.sync.exceptions import CursorInvalidError


@dataclass
class SyncCursor:
    """
    Decoded cursor containing pagination state.

    Attributes:
        timestamp: The updated_at timestamp of the last seen record
        entity_id: The id of the last seen record (for tiebreaking)
    """

    timestamp: datetime
    entity_id: str

    def __str__(self) -> str:
        return f"SyncCursor({self.timestamp.isoformat()}, {self.entity_id})"


def encode_cursor(timestamp: datetime, entity_id: str) -> str:
    """
    Encode a cursor for client consumption.

    The cursor is base64-encoded JSON containing timestamp and entity ID.
    This makes it opaque to clients while remaining debuggable.

    Args:
        timestamp: The updated_at timestamp
        entity_id: The entity ID for tiebreaking

    Returns:
        Base64-encoded cursor string
    """
    data = {
        "ts": timestamp.isoformat(),
        "id": entity_id,
    }
    json_str = json.dumps(data, separators=(",", ":"))
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> SyncCursor:
    """
    Decode a cursor from the client.

    Args:
        cursor: Base64-encoded cursor string

    Returns:
        SyncCursor with timestamp and entity_id

    Raises:
        CursorInvalidError: If cursor cannot be decoded or is malformed
    """
    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        data = json.loads(json_str)

        timestamp = datetime.fromisoformat(data["ts"])
        entity_id = data["id"]

        return SyncCursor(timestamp=timestamp, entity_id=entity_id)
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise CursorInvalidError(f"Invalid cursor format: {e}") from e


def parse_cursor(cursor: str | None) -> SyncCursor | None:
    """
    Parse an optional cursor string.

    Convenience function that returns None for None input.

    Args:
        cursor: Optional cursor string

    Returns:
        SyncCursor or None
    """
    if cursor is None:
        return None
    return decode_cursor(cursor)
