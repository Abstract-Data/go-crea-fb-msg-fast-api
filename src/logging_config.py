"""Centralized logging configuration with Pydantic Logfire integration."""

import logging
from typing import Any

import logfire
from fastapi import FastAPI

from src.config import get_settings


def setup_logfire(app: FastAPI) -> None:
    """
    Initialize and configure Pydantic Logfire for observability.

    Sets up:
    - FastAPI instrumentation (request/response tracing)
    - Pydantic instrumentation (model validation logging)
    - Environment-aware configuration
    - Structured JSON logging for production
    """
    settings = get_settings()

    # Configure Logfire (project_name is deprecated and not needed)
    logfire_config: dict[str, Any] = {
        "environment": settings.env,
    }

    # Add token if provided (for cloud logging)
    if hasattr(settings, "logfire_token") and settings.logfire_token:
        logfire_config["token"] = settings.logfire_token

    # Initialize Logfire
    logfire.configure(**logfire_config)

    # Instrument FastAPI (requires app) and Pydantic
    logfire.instrument_fastapi(app)
    logfire.instrument_pydantic()

    # Instrument PydanticAI for AI observability (pairs with PAIG)
    try:
        logfire.instrument_pydantic_ai()
    except AttributeError:
        # Fallback if instrument_pydantic_ai is not available
        pass

    # Configure Python logging based on environment
    log_level = getattr(settings, "log_level", "INFO").upper()

    if settings.env == "local":
        # Local: Console formatting for development
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        # Production: Structured JSON logging
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(message)s",  # Logfire handles structured formatting
        )


def mask_pii(value: str | None, mask_char: str = "*") -> str:
    """
    Mask potentially sensitive data in logs.

    Args:
        value: Value to mask
        mask_char: Character to use for masking

    Returns:
        Masked string
    """
    if not value:
        return ""

    if len(value) <= 4:
        return mask_char * len(value)

    # Show first 2 and last 2 characters, mask the rest
    return f"{value[:2]}{mask_char * (len(value) - 4)}{value[-2:]}"


def redact_tokens(data: dict[str, Any]) -> dict[str, Any]:
    """
    Redact authentication tokens and API keys from log data.

    Args:
        data: Dictionary that may contain sensitive tokens

    Returns:
        Dictionary with tokens redacted
    """
    redacted = data.copy()
    sensitive_keys = [
        "token",
        "access_token",
        "api_key",
        "secret",
        "password",
        "authorization",
        "auth",
    ]

    for key in sensitive_keys:
        if key in redacted:
            if isinstance(redacted[key], str):
                redacted[key] = mask_pii(redacted[key])
            elif isinstance(redacted[key], dict):
                redacted[key] = redact_tokens(redacted[key])

    return redacted
