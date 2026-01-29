"""Unit tests for the rate limiter middleware."""

import time
from datetime import datetime, timedelta
from unittest.mock import patch


from src.middleware.rate_limiter import (
    RateLimiter,
    get_rate_limiter,
    reset_rate_limiter,
)


class TestRateLimiter:
    """Test suite for the RateLimiter class."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def teardown_method(self):
        """Reset rate limiter after each test."""
        reset_rate_limiter()

    def test_allows_requests_under_limit(self):
        """Requests under the limit should be allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        user_id = "user123"

        for _ in range(5):
            assert limiter.check_rate_limit(user_id) is True

    def test_blocks_requests_over_limit(self):
        """Requests over the limit should be blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        user_id = "user123"

        # First 3 should succeed
        for _ in range(3):
            assert limiter.check_rate_limit(user_id) is True

        # 4th should fail
        assert limiter.check_rate_limit(user_id) is False

    def test_different_users_have_separate_limits(self):
        """Each user should have their own rate limit."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # User 1 uses their limit
        assert limiter.check_rate_limit("user1") is True
        assert limiter.check_rate_limit("user1") is True
        assert limiter.check_rate_limit("user1") is False

        # User 2 should still have their full limit
        assert limiter.check_rate_limit("user2") is True
        assert limiter.check_rate_limit("user2") is True
        assert limiter.check_rate_limit("user2") is False

    def test_window_expiry_allows_new_requests(self):
        """After window expires, new requests should be allowed."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        user_id = "user123"

        # Use up the limit
        assert limiter.check_rate_limit(user_id) is True
        assert limiter.check_rate_limit(user_id) is True
        assert limiter.check_rate_limit(user_id) is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.check_rate_limit(user_id) is True

    def test_sliding_window_behavior(self):
        """Window should slide, not reset completely."""
        limiter = RateLimiter(max_requests=2, window_seconds=2)
        user_id = "user123"

        # First request
        assert limiter.check_rate_limit(user_id) is True

        time.sleep(0.5)

        # Second request
        assert limiter.check_rate_limit(user_id) is True

        # Third should fail
        assert limiter.check_rate_limit(user_id) is False

        # Wait for first request to expire (not second)
        time.sleep(1.6)

        # Should allow one more request (second request still in window)
        assert limiter.check_rate_limit(user_id) is True
        assert limiter.check_rate_limit(user_id) is False

    def test_get_remaining_requests(self):
        """Should correctly report remaining requests."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        user_id = "user123"

        assert limiter.get_remaining_requests(user_id) == 5

        limiter.check_rate_limit(user_id)
        assert limiter.get_remaining_requests(user_id) == 4

        limiter.check_rate_limit(user_id)
        limiter.check_rate_limit(user_id)
        assert limiter.get_remaining_requests(user_id) == 2

    def test_reset_single_user(self):
        """Should reset rate limit for a single user."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        limiter.check_rate_limit("user1")
        limiter.check_rate_limit("user1")
        limiter.check_rate_limit("user2")

        # User 1 is at limit, user 2 has 1 remaining
        assert limiter.get_remaining_requests("user1") == 0
        assert limiter.get_remaining_requests("user2") == 1

        # Reset only user 1
        limiter.reset("user1")

        assert limiter.get_remaining_requests("user1") == 2
        assert limiter.get_remaining_requests("user2") == 1

    def test_reset_all_users(self):
        """Should reset rate limits for all users."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        limiter.check_rate_limit("user1")
        limiter.check_rate_limit("user2")

        limiter.reset()

        assert limiter.get_remaining_requests("user1") == 2
        assert limiter.get_remaining_requests("user2") == 2

    def test_get_window_reset_time(self):
        """Should return when the window will reset."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        user_id = "user123"

        # No requests, no reset time
        assert limiter.get_window_reset_time(user_id) is None

        # Make a request
        limiter.check_rate_limit(user_id)

        reset_time = limiter.get_window_reset_time(user_id)
        assert reset_time is not None
        assert reset_time > datetime.utcnow()
        assert reset_time < datetime.utcnow() + timedelta(seconds=61)

    def test_thread_safety(self):
        """Rate limiter should be thread-safe."""
        import threading

        limiter = RateLimiter(max_requests=100, window_seconds=60)
        user_id = "user123"
        results = []

        def make_request():
            result = limiter.check_rate_limit(user_id)
            results.append(result)

        threads = [threading.Thread(target=make_request) for _ in range(150)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 100 successes and 50 failures
        assert sum(results) == 100
        assert len(results) == 150


class TestRateLimiterGlobal:
    """Test the global rate limiter instance."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def teardown_method(self):
        """Reset rate limiter after each test."""
        reset_rate_limiter()

    def test_get_rate_limiter_returns_singleton(self):
        """get_rate_limiter should return the same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_reset_creates_new_instance(self):
        """reset_rate_limiter should clear the singleton."""
        limiter1 = get_rate_limiter()
        reset_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is not limiter2

    def test_global_limiter_uses_default_config(self):
        """Global limiter should use values from constants."""
        from src.constants import (
            MAX_MESSAGES_PER_USER_PER_MINUTE,
            RATE_LIMIT_WINDOW_SECONDS,
        )

        limiter = get_rate_limiter()

        assert limiter._max_requests == MAX_MESSAGES_PER_USER_PER_MINUTE
        assert limiter._window.total_seconds() == RATE_LIMIT_WINDOW_SECONDS


class TestRateLimiterLogging:
    """Test rate limiter logging behavior."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def teardown_method(self):
        """Reset rate limiter after each test."""
        reset_rate_limiter()

    def test_logs_warning_when_limit_exceeded(self):
        """Should log a warning when rate limit is exceeded."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        with patch("src.middleware.rate_limiter.logfire") as mock_logfire:
            limiter.check_rate_limit("user123")  # First succeeds
            limiter.check_rate_limit("user123")  # Second exceeds

            mock_logfire.warning.assert_called_once()
            call_kwargs = mock_logfire.warning.call_args[1]
            assert call_kwargs["user_id"] == "user123"
            assert call_kwargs["request_count"] == 1
            assert call_kwargs["max_requests"] == 1
