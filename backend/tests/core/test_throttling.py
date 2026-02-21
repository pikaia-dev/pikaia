"""
Tests for the rate limiting utility.
"""

import pytest
from django.core.cache import cache

from apps.core.throttling import (
    RateLimitExceeded,
    check_rate_limit,
    increment_rate_limit,
    peek_rate_limit,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestCheckRateLimit:
    """Tests for the check_rate_limit function."""

    def test_allows_requests_under_limit(self) -> None:
        """Should allow requests when under the limit."""
        for _ in range(5):
            check_rate_limit("test_key", max_requests=5, window_seconds=60)

    def test_blocks_requests_at_limit(self) -> None:
        """Should raise RateLimitExceeded when limit is reached."""
        for _ in range(3):
            check_rate_limit("test_key", max_requests=3, window_seconds=60)

        with pytest.raises(RateLimitExceeded) as exc_info:
            check_rate_limit("test_key", max_requests=3, window_seconds=60)

        assert exc_info.value.retry_after == 60
        assert "Too many requests" in str(exc_info.value)

    def test_separate_keys_independent(self) -> None:
        """Different keys should have independent counters."""
        for _ in range(3):
            check_rate_limit("key_a", max_requests=3, window_seconds=60)

        # key_b should still work
        check_rate_limit("key_b", max_requests=3, window_seconds=60)

        # key_a should be blocked
        with pytest.raises(RateLimitExceeded):
            check_rate_limit("key_a", max_requests=3, window_seconds=60)

    def test_retry_after_matches_window(self) -> None:
        """retry_after should match the configured window."""
        check_rate_limit("test_key", max_requests=1, window_seconds=900)

        with pytest.raises(RateLimitExceeded) as exc_info:
            check_rate_limit("test_key", max_requests=1, window_seconds=900)

        assert exc_info.value.retry_after == 900

    def test_increments_counter(self) -> None:
        """Counter should increment with each call."""
        check_rate_limit("test_key", max_requests=10, window_seconds=60)
        assert cache.get("rate_limit:test_key") == 1

        check_rate_limit("test_key", max_requests=10, window_seconds=60)
        assert cache.get("rate_limit:test_key") == 2


@pytest.mark.django_db
class TestPeekRateLimit:
    """Tests for the peek_rate_limit function (check without increment)."""

    def test_allows_when_no_counter_exists(self) -> None:
        """Should not raise when the rate limit key does not exist yet."""
        peek_rate_limit("fresh_key", max_requests=3, window_seconds=60)

    def test_allows_when_under_limit(self) -> None:
        """Should not raise when counter is under the limit."""
        cache.set("rate_limit:peek_key", 2, timeout=60)

        peek_rate_limit("peek_key", max_requests=3, window_seconds=60)

    def test_blocks_when_over_limit(self) -> None:
        """Should raise RateLimitExceeded when counter exceeds the limit."""
        cache.set("rate_limit:peek_key", 4, timeout=60)

        with pytest.raises(RateLimitExceeded) as exc_info:
            peek_rate_limit("peek_key", max_requests=3, window_seconds=60)

        assert exc_info.value.retry_after == 60

    def test_blocks_when_at_limit(self) -> None:
        """Should raise RateLimitExceeded when counter equals the limit exactly."""
        cache.set("rate_limit:peek_key", 3, timeout=60)

        with pytest.raises(RateLimitExceeded) as exc_info:
            peek_rate_limit("peek_key", max_requests=3, window_seconds=60)

        assert exc_info.value.retry_after == 60

    def test_does_not_increment_counter(self) -> None:
        """Should not change the counter value."""
        cache.set("rate_limit:peek_key", 2, timeout=60)

        peek_rate_limit("peek_key", max_requests=3, window_seconds=60)

        assert cache.get("rate_limit:peek_key") == 2


@pytest.mark.django_db
class TestIncrementRateLimit:
    """Tests for the increment_rate_limit function (increment without check)."""

    def test_creates_counter_when_none_exists(self) -> None:
        """Should create a counter starting at 1 when key does not exist."""
        increment_rate_limit("new_key", window_seconds=60)

        assert cache.get("rate_limit:new_key") == 1

    def test_increments_existing_counter(self) -> None:
        """Should increment an existing counter."""
        cache.set("rate_limit:inc_key", 3, timeout=60)

        increment_rate_limit("inc_key", window_seconds=60)

        assert cache.get("rate_limit:inc_key") == 4

    def test_does_not_raise_when_over_limit(self) -> None:
        """Should not raise even when counter exceeds any limit -- that is peek's job."""
        cache.set("rate_limit:inc_key", 100, timeout=60)

        increment_rate_limit("inc_key", window_seconds=60)

        assert cache.get("rate_limit:inc_key") == 101
