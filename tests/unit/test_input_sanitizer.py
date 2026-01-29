"""Unit tests for the input sanitization service."""


from src.constants import MAX_MESSAGE_LENGTH_CHARS
from src.services.input_sanitizer import (
    ValidationResult,
    get_user_friendly_error,
    is_valid_message,
    sanitize_user_input,
    validate_message,
)


class TestSanitizeUserInput:
    """Test suite for the sanitize_user_input function."""

    def test_empty_string_returns_empty(self):
        """Empty input should return empty string."""
        assert sanitize_user_input("") == ""

    def test_none_returns_empty(self):
        """None input should return empty string."""
        assert sanitize_user_input(None) == ""  # type: ignore

    def test_strips_whitespace(self):
        """Should strip leading and trailing whitespace."""
        assert sanitize_user_input("  hello world  ") == "hello world"
        assert sanitize_user_input("\n\nhello\n\n") == "hello"
        assert sanitize_user_input("\t\thello\t\t") == "hello"

    def test_removes_control_characters(self):
        """Should remove control characters except newlines/tabs."""
        # ASCII control characters (0-31 except \t, \n, \r)
        text_with_controls = "hello\x00\x01\x02\x03world"
        result = sanitize_user_input(text_with_controls)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "helloworld" == result

    def test_preserves_newlines_tabs(self):
        """Should preserve newlines and tabs."""
        text = "hello\nworld\tthere"
        result = sanitize_user_input(text)
        assert "\n" in result
        assert "\t" not in result  # tabs are collapsed to spaces
        assert "hello\nworld there" == result

    def test_collapses_multiple_spaces(self):
        """Should collapse multiple spaces to single space."""
        assert sanitize_user_input("hello    world") == "hello world"
        assert sanitize_user_input("hello  \t  world") == "hello world"

    def test_limits_consecutive_newlines(self):
        """Should limit consecutive newlines to 2."""
        text = "hello\n\n\n\n\nworld"
        result = sanitize_user_input(text)
        assert "\n\n\n" not in result
        assert result == "hello\n\nworld"

    def test_truncates_long_messages(self):
        """Should truncate messages exceeding max length."""
        long_text = "a" * (MAX_MESSAGE_LENGTH_CHARS + 100)
        result = sanitize_user_input(long_text)
        assert len(result) == MAX_MESSAGE_LENGTH_CHARS

    def test_unicode_normalization(self):
        """Should normalize Unicode to NFC form."""
        # é can be represented as single char or e + combining accent
        composed = "caf\u00e9"  # Single é character
        decomposed = "cafe\u0301"  # e + combining acute accent

        result1 = sanitize_user_input(composed)
        result2 = sanitize_user_input(decomposed)

        assert result1 == result2  # Both should normalize to same form

    def test_removes_null_bytes(self):
        """Should remove null bytes."""
        text = "hello\x00world"
        result = sanitize_user_input(text)
        assert "\x00" not in result
        assert result == "helloworld"

    def test_preserves_emoji(self):
        """Should preserve emoji characters."""
        text = "Hello 👋 World 🌍!"
        result = sanitize_user_input(text)
        assert "👋" in result
        assert "🌍" in result

    def test_preserves_non_latin_text(self):
        """Should preserve non-Latin scripts."""
        texts = [
            "こんにちは世界",  # Japanese
            "你好世界",  # Chinese
            "مرحبا بالعالم",  # Arabic
            "שלום עולם",  # Hebrew
            "Привет мир",  # Russian
        ]
        for text in texts:
            result = sanitize_user_input(text)
            assert result == text


class TestValidateMessage:
    """Test suite for the validate_message function."""

    def test_valid_message_passes(self):
        """Normal messages should pass validation."""
        result = validate_message("Hello, how are you?")

        assert result.is_valid is True
        assert result.error_code is None
        assert result.error_message is None

    def test_none_fails_validation(self):
        """None should fail validation."""
        result = validate_message(None)  # type: ignore

        assert result.is_valid is False
        assert result.error_code == "null_message"

    def test_empty_string_fails_validation(self):
        """Empty string should fail validation."""
        result = validate_message("")

        assert result.is_valid is False
        assert result.error_code == "empty_message"

    def test_whitespace_only_fails_validation(self):
        """Whitespace-only string should fail validation."""
        result = validate_message("   \n\t  ")

        assert result.is_valid is False
        assert result.error_code == "empty_message"

    def test_too_long_message_fails_validation(self):
        """Messages exceeding max length should fail."""
        long_text = "a" * (MAX_MESSAGE_LENGTH_CHARS + 1)
        result = validate_message(long_text)

        assert result.is_valid is False
        assert result.error_code == "message_too_long"
        assert str(MAX_MESSAGE_LENGTH_CHARS) in result.error_message

    def test_max_length_message_passes(self):
        """Message exactly at max length should pass."""
        exact_text = "a" * MAX_MESSAGE_LENGTH_CHARS
        result = validate_message(exact_text)

        assert result.is_valid is True

    def test_emoji_only_message_passes(self):
        """Emoji-only messages should pass (logged but not rejected)."""
        result = validate_message("🎉🎊🎁")

        assert result.is_valid is True

    def test_symbols_only_message_passes(self):
        """Symbol-only messages should pass (logged but not rejected)."""
        result = validate_message("!@#$%^&*()")

        assert result.is_valid is True


class TestIsValidMessage:
    """Test the simplified is_valid_message function."""

    def test_valid_message(self):
        """Valid message should return (True, None)."""
        is_valid, error = is_valid_message("Hello!")

        assert is_valid is True
        assert error is None

    def test_invalid_message(self):
        """Invalid message should return (False, error_code)."""
        is_valid, error = is_valid_message("")

        assert is_valid is False
        assert error == "empty_message"


class TestGetUserFriendlyError:
    """Test the get_user_friendly_error function."""

    def test_message_too_long_has_friendly_message(self):
        """message_too_long should have a user-friendly response."""
        message = get_user_friendly_error("message_too_long")

        assert message is not None
        assert "too long" in message.lower()
        assert "1000" in message  # Should mention the limit

    def test_empty_message_returns_none(self):
        """empty_message should not have a user response (don't respond to empty)."""
        message = get_user_friendly_error("empty_message")

        assert message is None

    def test_null_message_returns_none(self):
        """null_message should not have a user response."""
        message = get_user_friendly_error("null_message")

        assert message is None

    def test_unknown_error_returns_none(self):
        """Unknown error codes should return None."""
        message = get_user_friendly_error("unknown_error")

        assert message is None

    def test_none_returns_none(self):
        """None error code should return None."""
        message = get_user_friendly_error(None)

        assert message is None


class TestValidationResult:
    """Test the ValidationResult named tuple."""

    def test_validation_result_unpacking(self):
        """ValidationResult should support tuple unpacking."""
        result = ValidationResult(
            is_valid=False,
            error_code="test_error",
            error_message="Test error message",
        )

        is_valid, error_code, error_message = result

        assert is_valid is False
        assert error_code == "test_error"
        assert error_message == "Test error message"

    def test_validation_result_attribute_access(self):
        """ValidationResult should support named attribute access."""
        result = ValidationResult(
            is_valid=True,
            error_code=None,
            error_message=None,
        )

        assert result.is_valid is True
        assert result.error_code is None
        assert result.error_message is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_character_valid(self):
        """Single character should be valid."""
        result = validate_message("a")
        assert result.is_valid is True

    def test_very_long_whitespace_invalid(self):
        """Very long whitespace-only string should be invalid."""
        result = validate_message(" " * 10000)
        assert result.is_valid is False
        assert result.error_code == "empty_message"

    def test_newlines_only_invalid(self):
        """Newlines-only string should be invalid."""
        result = validate_message("\n\n\n")
        assert result.is_valid is False
        assert result.error_code == "empty_message"

    def test_mixed_control_and_text(self):
        """Text with control characters should be sanitizable."""
        text = "\x00Hello\x01World\x02"
        result = sanitize_user_input(text)
        assert result == "HelloWorld"

    def test_sanitize_preserves_valid_punctuation(self):
        """Sanitization should preserve valid punctuation."""
        text = "Hello! How are you? I'm fine, thanks."
        result = sanitize_user_input(text)
        assert result == text

    def test_sanitize_handles_urls(self):
        """URLs should be preserved during sanitization."""
        text = "Check out https://example.com/path?query=value&other=123"
        result = sanitize_user_input(text)
        assert "https://example.com" in result
