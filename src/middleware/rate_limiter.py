"""Rate limiting middleware for user messages.

Implements the rate limiting requirement from GUARDRAILS.md:
"Max 10 messages per user per minute"
"""

from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

import logfire

from src.constants import MAX_MESSAGES_PER_USER_PER_MINUTE, RATE_LIMIT_WINDOW_SECONDS


class RateLimiter:
    """Thread-safe in-memory rate limiter for user messages.

    Uses a sliding window approach to track requests per user.
    """

    def __init__(
        self,
        max_requests: int = MAX_MESSAGES_PER_USER_PER_MINUTE,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum allowed requests per window.
            window_seconds: Size of the sliding window in seconds.
        """
        self._requests: dict[str, list[datetime]] = defaultdict(list)
        self._max_requests = max_requests
        self._window = timedelta(seconds=window_seconds)
        self._lock = Lock()

    def check_rate_limit(self, user_id: str) -> bool:
        """Check if a user is within their rate limit.

        Args:
            user_id: The unique identifier for the user (sender_id).

        Returns:
            True if the user is within their rate limit, False if exceeded.
        """
        now = datetime.utcnow()
        cutoff = now - self._window

        with self._lock:
            # Remove old requests outside the current window
            self._requests[user_id] = [
                ts for ts in self._requests[user_id] if ts > cutoff
            ]

            if len(self._requests[user_id]) >= self._max_requests:
                logfire.warning(
                    "Rate limit exceeded",
                    user_id=user_id,
                    request_count=len(self._requests[user_id]),
                    max_requests=self._max_requests,
                    window_seconds=self._window.total_seconds(),
                )
                return False

            # Record this request
            self._requests[user_id].append(now)
            return True

    def get_remaining_requests(self, user_id: str) -> int:
        """Get the number of remaining requests for a user.

        Args:
            user_id: The unique identifier for the user.

        Returns:
            Number of remaining requests in the current window.
        """
        now = datetime.utcnow()
        cutoff = now - self._window

        with self._lock:
            # Clean up old requests
            self._requests[user_id] = [
                ts for ts in self._requests[user_id] if ts > cutoff
            ]
            return max(0, self._max_requests - len(self._requests[user_id]))

    def reset(self, user_id: str | None = None) -> None:
        """Reset rate limit tracking.

        Args:
            user_id: If provided, reset only for this user. Otherwise reset all.
        """
        with self._lock:
            if user_id:
                self._requests.pop(user_id, None)
            else:
                self._requests.clear()

    def get_window_reset_time(self, user_id: str) -> datetime | None:
        """Get when the oldest request in the window will expire.

        Args:
            user_id: The unique identifier for the user.

        Returns:
            Datetime when the oldest request expires, or None if no requests.
        """
        now = datetime.utcnow()
        cutoff = now - self._window

        with self._lock:
            # Clean up old requests
            self._requests[user_id] = [
                ts for ts in self._requests[user_id] if ts > cutoff
            ]
            if self._requests[user_id]:
                oldest = min(self._requests[user_id])
                return oldest + self._window
            return None


# Global instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance.

    Returns:
        The singleton RateLimiter instance.
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (primarily for testing)."""
    global _rate_limiter
    _rate_limiter = None
