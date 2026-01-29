"""Tests for database query executor utilities."""

import time
from unittest.mock import patch

import pytest

from src.db.query_executor import QueryTimer, timed_query


class TestTimedQuery:
    """Tests for the timed_query context manager."""

    def test_successful_query_logs_start_and_completion(self):
        """Successful query should log start and completion with timing."""
        with patch("src.db.query_executor.logfire") as mock_logfire:
            with timed_query("test_operation", user_id="123"):
                # Simulate some work
                time.sleep(0.01)

            # Should have logged start
            assert mock_logfire.info.call_count == 2

            start_call = mock_logfire.info.call_args_list[0]
            assert "Starting test_operation" in start_call[0][0]
            assert start_call[1]["operation"] == "test_operation"
            assert start_call[1]["user_id"] == "123"

            # Should have logged completion with timing
            completion_call = mock_logfire.info.call_args_list[1]
            assert "test_operation completed" in completion_call[0][0]
            assert completion_call[1]["operation"] == "test_operation"
            assert "response_time_ms" in completion_call[1]
            assert completion_call[1]["response_time_ms"] > 0

    def test_failed_query_logs_error_and_reraises(self):
        """Failed query should log error with timing and re-raise exception."""
        with patch("src.db.query_executor.logfire") as mock_logfire:
            with pytest.raises(ValueError, match="test error"):
                with timed_query("test_operation", page_id="456"):
                    raise ValueError("test error")

            # Should have logged start
            assert mock_logfire.info.call_count == 1

            # Should have logged error
            assert mock_logfire.error.call_count == 1

            error_call = mock_logfire.error.call_args
            assert "test_operation failed" in error_call[0][0]
            assert error_call[1]["operation"] == "test_operation"
            assert error_call[1]["error"] == "test error"
            assert error_call[1]["error_type"] == "ValueError"
            assert "response_time_ms" in error_call[1]
            assert error_call[1]["page_id"] == "456"

    def test_context_passes_through_log_context(self):
        """All log_context kwargs should be passed to all log calls."""
        with patch("src.db.query_executor.logfire") as mock_logfire:
            with timed_query(
                "multi_context_op",
                sender_id="sender123",
                page_id="page456",
                extra_field="extra_value",
            ):
                pass

            # Check both calls have all context
            for call in mock_logfire.info.call_args_list:
                assert call[1]["sender_id"] == "sender123"
                assert call[1]["page_id"] == "page456"
                assert call[1]["extra_field"] == "extra_value"

    def test_timing_is_accurate(self):
        """Timing should be reasonably accurate."""
        with patch("src.db.query_executor.logfire") as mock_logfire:
            sleep_duration_ms = 50

            with timed_query("timing_test"):
                time.sleep(sleep_duration_ms / 1000)

            completion_call = mock_logfire.info.call_args_list[1]
            elapsed_ms = completion_call[1]["response_time_ms"]

            # Should be close to sleep duration (allow some tolerance)
            assert elapsed_ms >= sleep_duration_ms * 0.9
            assert elapsed_ms < sleep_duration_ms * 2  # Allow up to 2x for CI variance


class TestQueryTimer:
    """Tests for the QueryTimer class."""

    def test_basic_success_flow(self):
        """Basic success flow should work correctly."""
        with patch("src.db.query_executor.logfire") as mock_logfire:
            timer = QueryTimer("test_op", key="value")
            timer.start()
            time.sleep(0.01)
            elapsed = timer.success(result_count=5)

            assert elapsed > 0
            assert timer.elapsed_ms == elapsed

            # Check start log
            start_call = mock_logfire.info.call_args_list[0]
            assert "Starting test_op" in start_call[0][0]
            assert start_call[1]["key"] == "value"

            # Check success log
            success_call = mock_logfire.info.call_args_list[1]
            assert "test_op completed" in success_call[0][0]
            assert success_call[1]["result_count"] == 5

    def test_error_flow(self):
        """Error flow should log error correctly."""
        with patch("src.db.query_executor.logfire") as mock_logfire:
            timer = QueryTimer("failing_op", doc_id="doc123")
            timer.start()

            exc = RuntimeError("Something went wrong")
            elapsed = timer.error(exc, extra_info="debug_data")

            assert elapsed > 0
            assert timer.elapsed_ms == elapsed

            # Check error log
            error_call = mock_logfire.error.call_args
            assert "failing_op failed" in error_call[0][0]
            assert error_call[1]["error"] == "Something went wrong"
            assert error_call[1]["error_type"] == "RuntimeError"
            assert error_call[1]["doc_id"] == "doc123"
            assert error_call[1]["extra_info"] == "debug_data"

    def test_success_without_start_raises(self):
        """Calling success() without start() should raise RuntimeError."""
        timer = QueryTimer("unstarted_op")

        with pytest.raises(RuntimeError, match="Timer was not started"):
            timer.success()

    def test_error_without_start_raises(self):
        """Calling error() without start() should raise RuntimeError."""
        timer = QueryTimer("unstarted_op")

        with pytest.raises(RuntimeError, match="Timer was not started"):
            timer.error(ValueError("test"))

    def test_elapsed_ms_is_none_before_completion(self):
        """elapsed_ms should be None before success/error is called."""
        timer = QueryTimer("pending_op")
        assert timer.elapsed_ms is None

        timer.start()
        assert timer.elapsed_ms is None

    def test_start_returns_self_for_chaining(self):
        """start() should return self for method chaining."""
        with patch("src.db.query_executor.logfire"):
            timer = QueryTimer("chainable_op")
            result = timer.start()
            assert result is timer
            timer.success()
