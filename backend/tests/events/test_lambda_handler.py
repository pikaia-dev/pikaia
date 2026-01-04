"""
Tests for standalone Lambda event publisher.
"""

import importlib
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import apps.events.lambda_handler as lh


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("EVENT_BUS_NAME", "test-bus")
    monkeypatch.setenv("BATCH_SIZE", "10")
    monkeypatch.setenv("MAX_ATTEMPTS", "10")
    # Reload to pick up env vars
    importlib.reload(lh)


@pytest.fixture
def sample_events():
    """Sample events from the outbox."""
    return [
        {
            "id": 1,
            "event_type": "organization.created",
            "payload": {
                "event_id": str(uuid4()),
                "event_type": "organization.created",
                "data": {"name": "Test Org"},
            },
        },
        {
            "id": 2,
            "event_type": "member.invited",
            "payload": {
                "event_id": str(uuid4()),
                "event_type": "member.invited",
                "data": {"email": "test@example.com"},
            },
        },
    ]


class TestLambdaPublishPendingEvents:
    """Tests for publish_pending_events function."""

    def test_publish_pending_events_success(self, mock_env, sample_events):
        """Test successful event publishing."""
        with (
            patch("apps.events.lambda_handler.psycopg2") as mock_psycopg2,
            patch("apps.events.lambda_handler.boto3") as mock_boto3,
        ):
            # Mock database connection context manager
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = sample_events

            # Mock EventBridge
            mock_eb = MagicMock()
            mock_boto3.client.return_value = mock_eb
            mock_eb.put_events.return_value = {
                "Entries": [{"EventId": "eb-1"}, {"EventId": "eb-2"}]
            }

            count = lh.publish_pending_events()

            assert count == 2
            mock_eb.put_events.assert_called_once()
            # Verify UPDATE was called for published events
            assert mock_cursor.execute.call_count >= 2  # SELECT + UPDATE

    def test_no_pending_events(self, mock_env):
        """Test with no pending events."""
        with (
            patch("apps.events.lambda_handler.psycopg2") as mock_psycopg2,
            patch("apps.events.lambda_handler.boto3"),
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            count = lh.publish_pending_events()

            assert count == 0

    def test_eventbridge_per_entry_errors(self, mock_env, sample_events):
        """Test handling of per-entry EventBridge errors."""
        with (
            patch("apps.events.lambda_handler.psycopg2") as mock_psycopg2,
            patch("apps.events.lambda_handler.boto3") as mock_boto3,
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = sample_events

            mock_eb = MagicMock()
            mock_boto3.client.return_value = mock_eb
            # First succeeds, second fails
            mock_eb.put_events.return_value = {
                "Entries": [
                    {"EventId": "eb-1"},
                    {"ErrorCode": "ThrottlingException", "ErrorMessage": "Rate exceeded"},
                ]
            }

            count = lh.publish_pending_events()

            # Only 1 succeeded
            assert count == 1


class TestLambdaHandler:
    """Tests for the Lambda handler function."""

    def test_handler_returns_success(self, mock_env, sample_events):
        """Test handler returns 200 on success."""
        with (
            patch("apps.events.lambda_handler.psycopg2") as mock_psycopg2,
            patch("apps.events.lambda_handler.boto3") as mock_boto3,
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = sample_events

            mock_eb = MagicMock()
            mock_boto3.client.return_value = mock_eb
            mock_eb.put_events.return_value = {
                "Entries": [{"EventId": "eb-1"}, {"EventId": "eb-2"}]
            }

            result = lh.handler({}, None)

            assert result["statusCode"] == 200
            assert "2 events" in result["body"]

    def test_handler_no_events(self, mock_env):
        """Test handler with no pending events."""
        with (
            patch("apps.events.lambda_handler.psycopg2") as mock_psycopg2,
            patch("apps.events.lambda_handler.boto3"),
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            result = lh.handler({}, None)

            assert result["statusCode"] == 200
            assert "0 events" in result["body"]

    def test_handler_missing_database_url(self, monkeypatch):
        """Test handler fails gracefully without DATABASE_URL."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        # Reimport to pick up cleared env
        importlib.reload(lh)

        result = lh.handler({}, None)

        assert result["statusCode"] == 500
        assert "DATABASE_URL" in result["body"]

        # Restore for other tests
        monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
        importlib.reload(lh)

    def test_handler_database_error(self, mock_env):
        """Test handler handles database connection errors."""
        with patch("apps.events.lambda_handler.psycopg2") as mock_psycopg2:
            mock_psycopg2.connect.side_effect = Exception("Connection refused")

            result = lh.handler({}, None)

            assert result["statusCode"] == 500
            assert "Connection refused" in result["body"]
