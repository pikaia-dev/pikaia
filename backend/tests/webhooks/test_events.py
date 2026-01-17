"""
Tests for webhook event catalog.
"""


from apps.webhooks.events import (
    WEBHOOK_EVENTS,
    get_categories,
    get_event_type,
    get_event_types,
    get_events_by_category,
    is_valid_event_type,
    matches_subscription,
)


class TestEventCatalog:
    """Tests for the event catalog."""

    def test_has_member_events(self) -> None:
        """Should have member-related events."""
        assert "member.created" in WEBHOOK_EVENTS
        assert "member.deleted" in WEBHOOK_EVENTS
        assert "member.updated" in WEBHOOK_EVENTS
        assert "member.role_changed" in WEBHOOK_EVENTS

    def test_has_organization_events(self) -> None:
        """Should have organization-related events."""
        assert "organization.updated" in WEBHOOK_EVENTS

    def test_has_billing_events(self) -> None:
        """Should have billing-related events."""
        assert "billing.subscription_created" in WEBHOOK_EVENTS
        assert "billing.subscription_canceled" in WEBHOOK_EVENTS
        assert "billing.payment_succeeded" in WEBHOOK_EVENTS
        assert "billing.payment_failed" in WEBHOOK_EVENTS

    def test_all_events_have_required_fields(self) -> None:
        """All events should have type, description, category, and example."""
        for event_type, event in WEBHOOK_EVENTS.items():
            assert event.type == event_type
            assert event.description
            assert event.category
            assert isinstance(event.payload_example, dict)


class TestGetEventTypes:
    """Tests for get_event_types function."""

    def test_returns_all_events(self) -> None:
        """Should return all registered events."""
        events = get_event_types()

        assert len(events) == len(WEBHOOK_EVENTS)

    def test_returns_list_of_event_types(self) -> None:
        """Should return WebhookEventType objects."""
        events = get_event_types()

        assert all(hasattr(e, "type") for e in events)
        assert all(hasattr(e, "description") for e in events)


class TestGetEventType:
    """Tests for get_event_type function."""

    def test_returns_event_for_valid_type(self) -> None:
        """Should return event for valid type."""
        event = get_event_type("member.created")

        assert event is not None
        assert event.type == "member.created"

    def test_returns_none_for_invalid_type(self) -> None:
        """Should return None for invalid type."""
        event = get_event_type("invalid.event")

        assert event is None


class TestGetCategories:
    """Tests for get_categories function."""

    def test_returns_all_categories(self) -> None:
        """Should return all unique categories."""
        categories = get_categories()

        assert "member" in categories
        assert "organization" in categories
        assert "billing" in categories

    def test_returns_sorted_categories(self) -> None:
        """Should return categories in sorted order."""
        categories = get_categories()

        assert categories == sorted(categories)


class TestGetEventsByCategory:
    """Tests for get_events_by_category function."""

    def test_returns_events_for_category(self) -> None:
        """Should return all events in category."""
        member_events = get_events_by_category("member")

        assert all(e.category == "member" for e in member_events)
        assert len(member_events) >= 4  # At least created, updated, deleted, role_changed

    def test_returns_empty_for_invalid_category(self) -> None:
        """Should return empty list for invalid category."""
        events = get_events_by_category("invalid")

        assert events == []


class TestIsValidEventType:
    """Tests for is_valid_event_type function."""

    def test_accepts_exact_event_type(self) -> None:
        """Should accept exact event type matches."""
        assert is_valid_event_type("member.created") is True
        assert is_valid_event_type("billing.payment_succeeded") is True

    def test_rejects_invalid_event_type(self) -> None:
        """Should reject invalid event types."""
        assert is_valid_event_type("invalid.event") is False
        assert is_valid_event_type("member.nonexistent") is False

    def test_accepts_wildcard_for_valid_category(self) -> None:
        """Should accept wildcards for valid categories."""
        assert is_valid_event_type("member.*") is True
        assert is_valid_event_type("billing.*") is True
        assert is_valid_event_type("organization.*") is True

    def test_rejects_wildcard_for_invalid_category(self) -> None:
        """Should reject wildcards for invalid categories."""
        assert is_valid_event_type("invalid.*") is False
        assert is_valid_event_type("foo.*") is False


class TestMatchesSubscription:
    """Tests for matches_subscription function."""

    def test_matches_exact_subscription(self) -> None:
        """Should match exact event subscriptions."""
        assert matches_subscription("member.created", ["member.created"]) is True
        assert matches_subscription("member.created", ["member.deleted"]) is False

    def test_matches_wildcard_subscription(self) -> None:
        """Should match wildcard subscriptions."""
        assert matches_subscription("member.created", ["member.*"]) is True
        assert matches_subscription("member.deleted", ["member.*"]) is True
        assert matches_subscription("billing.payment_succeeded", ["member.*"]) is False

    def test_matches_mixed_subscriptions(self) -> None:
        """Should match when any subscription matches."""
        subscriptions = ["member.created", "billing.*"]

        assert matches_subscription("member.created", subscriptions) is True
        assert matches_subscription("billing.payment_succeeded", subscriptions) is True
        assert matches_subscription("member.deleted", subscriptions) is False
        assert matches_subscription("organization.updated", subscriptions) is False

    def test_empty_subscriptions_never_match(self) -> None:
        """Should never match with empty subscriptions."""
        assert matches_subscription("member.created", []) is False
