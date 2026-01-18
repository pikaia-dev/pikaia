"""Tests for webhook idempotency utilities."""

import pytest

from apps.core.models import ProcessedWebhook
from apps.core.webhooks import is_webhook_processed, mark_webhook_processed


@pytest.mark.django_db
class TestProcessedWebhookModel:
    """Tests for ProcessedWebhook model."""

    def test_creates_record(self) -> None:
        """Should create a processed webhook record."""
        webhook = ProcessedWebhook.objects.create(source="stripe", event_id="evt_123")

        assert webhook.source == "stripe"
        assert webhook.event_id == "evt_123"
        assert webhook.processed_at is not None

    def test_str_representation(self) -> None:
        """Should return source:event_id format."""
        webhook = ProcessedWebhook.objects.create(source="stytch", event_id="msg_456")

        assert str(webhook) == "stytch:msg_456"

    def test_unique_constraint(self) -> None:
        """Should prevent duplicate source/event_id combinations."""
        ProcessedWebhook.objects.create(source="stripe", event_id="evt_123")

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            ProcessedWebhook.objects.create(source="stripe", event_id="evt_123")

    def test_allows_same_event_id_different_sources(self) -> None:
        """Should allow same event_id with different sources."""
        ProcessedWebhook.objects.create(source="stripe", event_id="evt_123")
        ProcessedWebhook.objects.create(source="stytch", event_id="evt_123")

        assert ProcessedWebhook.objects.filter(event_id="evt_123").count() == 2


@pytest.mark.django_db
class TestIsWebhookProcessed:
    """Tests for is_webhook_processed function."""

    def test_returns_false_for_new_event(self) -> None:
        """Should return False for unprocessed event."""
        assert is_webhook_processed("stripe", "evt_new") is False

    def test_returns_true_for_processed_event(self) -> None:
        """Should return True for already processed event."""
        ProcessedWebhook.objects.create(source="stripe", event_id="evt_existing")

        assert is_webhook_processed("stripe", "evt_existing") is True

    def test_checks_source_separately(self) -> None:
        """Should check source when determining if processed."""
        ProcessedWebhook.objects.create(source="stripe", event_id="evt_123")

        assert is_webhook_processed("stripe", "evt_123") is True
        assert is_webhook_processed("stytch", "evt_123") is False


@pytest.mark.django_db
class TestMarkWebhookProcessed:
    """Tests for mark_webhook_processed function."""

    def test_marks_new_event_as_processed(self) -> None:
        """Should create record and return True for new event."""
        result = mark_webhook_processed("stripe", "evt_new")

        assert result is True
        assert ProcessedWebhook.objects.filter(source="stripe", event_id="evt_new").exists()

    def test_returns_false_for_duplicate(self) -> None:
        """Should return False for already processed event."""
        mark_webhook_processed("stripe", "evt_dup")
        result = mark_webhook_processed("stripe", "evt_dup")

        assert result is False

    def test_handles_race_condition(self) -> None:
        """Should handle concurrent inserts safely."""
        # First call succeeds
        assert mark_webhook_processed("stripe", "evt_race") is True
        # Second call returns False due to unique constraint
        assert mark_webhook_processed("stripe", "evt_race") is False
