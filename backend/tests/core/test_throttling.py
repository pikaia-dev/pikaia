"""
Tests for the rate limiting utility.
"""

import pytest
from django.core.cache import cache

from apps.core.throttling import RateLimitExceeded, check_rate_limit


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
