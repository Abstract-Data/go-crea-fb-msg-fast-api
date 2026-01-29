"""Database query execution utilities.

This module provides utilities for timing and logging database operations
to reduce code duplication across repository functions.
"""

import time
from contextlib import contextmanager
from typing import Any, Generator

import logfire


@contextmanager
def timed_query(
    operation_name: str,
    **log_context: Any,
) -> Generator[None, None, None]:
    """
    Context manager for timing and logging database operations.

    Logs the start of the operation, and on completion logs either success
    with elapsed time or error details if an exception occurred.

    Args:
        operation_name: Name of the database operation (e.g., "get_bot_configuration")
        **log_context: Additional context to include in all log messages

    Yields:
        None

    Example:
        with timed_query("get_user_profile", sender_id=sender_id, page_id=page_id):
            result = client.table("user_profiles").select("*").eq("sender_id", sender_id).execute()
    """
    start_time = time.time()

    logfire.info(
        f"Starting {operation_name}",
        operation=operation_name,
        **log_context,
    )

    try:
        yield
        elapsed = time.time() - start_time
        logfire.info(
            f"{operation_name} completed",
            operation=operation_name,
            response_time_ms=elapsed * 1000,
            **log_context,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logfire.error(
            f"{operation_name} failed",
            operation=operation_name,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
            **log_context,
        )
        raise


class QueryTimer:
    """
    Alternative class-based timer for operations that need to access elapsed time.

    Use this when you need to access the elapsed time after the query completes,
    or when you need more control over the timing.

    Example:
        timer = QueryTimer("search_page_chunks", reference_doc_id=doc_id)
        timer.start()
        try:
            result = client.rpc(...).execute()
            timer.success(result_count=len(result.data))
        except Exception as e:
            timer.error(e)
            raise
    """

    def __init__(self, operation_name: str, **log_context: Any):
        self.operation_name = operation_name
        self.log_context = log_context
        self._start_time: float | None = None
        self._elapsed_ms: float | None = None

    def start(self) -> "QueryTimer":
        """Start the timer and log the operation start."""
        self._start_time = time.time()
        logfire.info(
            f"Starting {self.operation_name}",
            operation=self.operation_name,
            **self.log_context,
        )
        return self

    def success(self, **extra_context: Any) -> float:
        """
        Mark operation as successful and log completion.

        Args:
            **extra_context: Additional context to include in success log

        Returns:
            Elapsed time in milliseconds
        """
        if self._start_time is None:
            raise RuntimeError("Timer was not started. Call start() first.")

        self._elapsed_ms = (time.time() - self._start_time) * 1000
        logfire.info(
            f"{self.operation_name} completed",
            operation=self.operation_name,
            response_time_ms=self._elapsed_ms,
            **self.log_context,
            **extra_context,
        )
        return self._elapsed_ms

    def error(self, exception: Exception, **extra_context: Any) -> float:
        """
        Mark operation as failed and log error.

        Args:
            exception: The exception that occurred
            **extra_context: Additional context to include in error log

        Returns:
            Elapsed time in milliseconds
        """
        if self._start_time is None:
            raise RuntimeError("Timer was not started. Call start() first.")

        self._elapsed_ms = (time.time() - self._start_time) * 1000
        logfire.error(
            f"{self.operation_name} failed",
            operation=self.operation_name,
            error=str(exception),
            error_type=type(exception).__name__,
            response_time_ms=self._elapsed_ms,
            **self.log_context,
            **extra_context,
        )
        return self._elapsed_ms

    @property
    def elapsed_ms(self) -> float | None:
        """Get elapsed time in milliseconds (None if not yet completed)."""
        return self._elapsed_ms
