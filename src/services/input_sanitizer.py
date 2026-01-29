"""Input validation and sanitization service.

Provides functions for validating and sanitizing user input
to ensure safe processing by the agent service.
"""

from typing import NamedTuple

import logfire

from src.constants import MAX_MESSAGE_LENGTH_CHARS


class ValidationResult(NamedTuple):
    """Result of input validation.

    Attributes:
        is_valid: Whether the input passed validation.
        error_code: Error code if validation failed, None otherwise.
        error_message: Human-readable error message if validation failed.
    """

    is_valid: bool
    error_code: str | None
    error_message: str | None


def sanitize_user_input(text: str) -> str:
    """Sanitize user input to prevent injection and ensure valid text.

    Performs the following sanitization:
    - Removes control characters (except newlines, carriage returns, tabs)
    - Normalizes whitespace (collapses multiple spaces/newlines)
    - Strips leading/trailing whitespace
    - Truncates to maximum allowed length

    Args:
        text: The raw user input text.

    Returns:
        Sanitized text safe for processing.
    """
    if not text:
        return ""

    # Remove control characters (keep newlines, carriage returns, tabs)
    sanitized = "".join(char for char in text if ord(char) >= 32 or char in "\n\r\t")

    # Normalize Unicode (NFC form - composed characters)
    import unicodedata

    sanitized = unicodedata.normalize("NFC", sanitized)

    # Remove null bytes and other problematic characters
    sanitized = sanitized.replace("\x00", "")

    # Collapse multiple whitespace (spaces, but preserve single newlines)
    import re

    sanitized = re.sub(r"[ \t]+", " ", sanitized)  # Collapse spaces/tabs
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)  # Max 2 consecutive newlines

    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()

    # Truncate if too long
    if len(sanitized) > MAX_MESSAGE_LENGTH_CHARS:
        logfire.warning(
            "Message truncated",
            original_length=len(sanitized),
            max_length=MAX_MESSAGE_LENGTH_CHARS,
        )
        sanitized = sanitized[:MAX_MESSAGE_LENGTH_CHARS]

    return sanitized


def validate_message(text: str) -> ValidationResult:
    """Validate user message text.

    Checks:
    - Not empty or whitespace-only
    - Not too long (before sanitization)
    - Contains at least some alphanumeric content

    Args:
        text: The raw user input text to validate.

    Returns:
        ValidationResult with validation status and error details.
    """
    # Check for None or empty
    if text is None:
        return ValidationResult(
            is_valid=False,
            error_code="null_message",
            error_message="Message cannot be null",
        )

    # Check for empty or whitespace-only
    stripped = text.strip()
    if not stripped:
        return ValidationResult(
            is_valid=False,
            error_code="empty_message",
            error_message="Message cannot be empty",
        )

    # Check length
    if len(text) > MAX_MESSAGE_LENGTH_CHARS:
        return ValidationResult(
            is_valid=False,
            error_code="message_too_long",
            error_message=f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH_CHARS} characters",
        )

    # Check for at least some meaningful content (not just symbols)
    import re

    if not re.search(r"[a-zA-Z0-9]", stripped):
        # Allow some emoji-only or symbol messages but log them
        logfire.info(
            "Message contains no alphanumeric characters",
            text_preview=stripped[:50],
        )
        # We don't reject these - users might send emoji responses

    return ValidationResult(
        is_valid=True,
        error_code=None,
        error_message=None,
    )


def is_valid_message(text: str) -> tuple[bool, str | None]:
    """Simplified validation check for backward compatibility.

    Args:
        text: The raw user input text to validate.

    Returns:
        Tuple of (is_valid, error_code).
    """
    result = validate_message(text)
    return result.is_valid, result.error_code


def get_user_friendly_error(error_code: str | None) -> str | None:
    """Get a user-friendly error message for sending back to the user.

    Args:
        error_code: The error code from validation.

    Returns:
        User-friendly message or None if no message needed.
    """
    error_messages = {
        "empty_message": None,  # Don't respond to empty messages
        "null_message": None,
        "message_too_long": "Your message is too long. Please send a shorter message (max 1000 characters).",
    }
    return error_messages.get(error_code)
