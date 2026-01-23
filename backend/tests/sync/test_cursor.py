"""
Tests for cursor encoding and decoding.
"""

from datetime import UTC, datetime

import pytest

from apps.sync.cursor import SyncCursor, decode_cursor, encode_cursor, parse_cursor
from apps.sync.exceptions import CursorInvalidError


class TestCursorEncoding:
    """Tests for cursor encoding."""

    def test_encode_cursor_returns_string(self):
        """Should return a base64-encoded string."""
        timestamp = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        entity_id = "ct_01HN8J1234567890ABCDEF"

        cursor = encode_cursor(timestamp, entity_id)

        assert isinstance(cursor, str)
        assert len(cursor) > 0

    def test_encode_cursor_is_url_safe(self):
        """Should produce URL-safe base64 encoding."""
        timestamp = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        entity_id = "ct_01HN8J1234567890ABCDEF"

        cursor = encode_cursor(timestamp, entity_id)

        # URL-safe base64 doesn't contain + or /
        assert "+" not in cursor
        assert "/" not in cursor

    def test_encode_cursor_different_inputs_different_outputs(self):
        """Different inputs should produce different cursors."""
        ts1 = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        ts2 = datetime(2025, 1, 23, 10, 31, 0, tzinfo=UTC)
        id1 = "ct_01HN8J1234567890ABCDEF"
        id2 = "ct_01HN8J1234567890GHIJKL"

        cursor1 = encode_cursor(ts1, id1)
        cursor2 = encode_cursor(ts1, id2)
        cursor3 = encode_cursor(ts2, id1)

        assert cursor1 != cursor2
        assert cursor1 != cursor3
        assert cursor2 != cursor3


class TestCursorDecoding:
    """Tests for cursor decoding."""

    def test_decode_cursor_roundtrip(self):
        """Should decode to same values that were encoded."""
        timestamp = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        entity_id = "ct_01HN8J1234567890ABCDEF"

        cursor = encode_cursor(timestamp, entity_id)
        decoded = decode_cursor(cursor)

        assert decoded.timestamp == timestamp
        assert decoded.entity_id == entity_id

    def test_decode_cursor_returns_sync_cursor(self):
        """Should return a SyncCursor dataclass."""
        timestamp = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        entity_id = "ct_01HN8J1234567890ABCDEF"

        cursor = encode_cursor(timestamp, entity_id)
        decoded = decode_cursor(cursor)

        assert isinstance(decoded, SyncCursor)

    def test_decode_cursor_invalid_base64_raises_error(self):
        """Should raise CursorInvalidError for invalid base64."""
        with pytest.raises(CursorInvalidError):
            decode_cursor("not-valid-base64!!!")

    def test_decode_cursor_invalid_json_raises_error(self):
        """Should raise CursorInvalidError for invalid JSON."""
        import base64

        invalid_json = base64.urlsafe_b64encode(b"not json").decode()

        with pytest.raises(CursorInvalidError):
            decode_cursor(invalid_json)

    def test_decode_cursor_missing_fields_raises_error(self):
        """Should raise CursorInvalidError if required fields missing."""
        import base64
        import json

        # Missing 'id' field
        incomplete = base64.urlsafe_b64encode(
            json.dumps({"ts": "2025-01-23T10:30:00+00:00"}).encode()
        ).decode()

        with pytest.raises(CursorInvalidError):
            decode_cursor(incomplete)

    def test_decode_cursor_invalid_timestamp_raises_error(self):
        """Should raise CursorInvalidError for invalid timestamp format."""
        import base64
        import json

        invalid_ts = base64.urlsafe_b64encode(
            json.dumps({"ts": "not-a-timestamp", "id": "ct_123"}).encode()
        ).decode()

        with pytest.raises(CursorInvalidError):
            decode_cursor(invalid_ts)


class TestParseCursor:
    """Tests for parse_cursor helper."""

    def test_parse_cursor_returns_none_for_none_input(self):
        """Should return None when input is None."""
        result = parse_cursor(None)

        assert result is None

    def test_parse_cursor_decodes_valid_cursor(self):
        """Should decode valid cursor string."""
        timestamp = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        entity_id = "ct_01HN8J1234567890ABCDEF"
        cursor = encode_cursor(timestamp, entity_id)

        result = parse_cursor(cursor)

        assert result is not None
        assert result.timestamp == timestamp
        assert result.entity_id == entity_id

    def test_parse_cursor_raises_on_invalid(self):
        """Should raise CursorInvalidError for invalid cursor."""
        with pytest.raises(CursorInvalidError):
            parse_cursor("invalid-cursor")


class TestSyncCursorDataclass:
    """Tests for SyncCursor dataclass."""

    def test_sync_cursor_str_representation(self):
        """Should have a readable string representation."""
        timestamp = datetime(2025, 1, 23, 10, 30, 0, tzinfo=UTC)
        entity_id = "ct_123"

        cursor = SyncCursor(timestamp=timestamp, entity_id=entity_id)

        str_repr = str(cursor)
        assert "2025-01-23" in str_repr
        assert "ct_123" in str_repr
