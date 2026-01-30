"""Application configuration using Pydantic BaseSettings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import (
    BROWSER_JS_REFETCH_TIMEOUT_SECONDS,
    BROWSER_PAGE_LOAD_TIMEOUT_SECONDS,
    DEFAULT_EMBEDDING_DIMENSIONS,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_SEARCH_RESULT_LIMIT,
    FACEBOOK_API_TIMEOUT_SECONDS,
    MAX_MESSAGES_PER_USER_PER_MINUTE,
    RATE_LIMIT_WINDOW_SECONDS,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Load .env first, then .env.local (for local/test overrides)
        # Later files override earlier ones, so .env.local takes precedence
        env_file=[".env", ".env.local"],
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Facebook Configuration
    facebook_page_access_token: str = Field(
        ..., description="Facebook Page access token"
    )
    facebook_verify_token: str = Field(..., description="Webhook verification token")
    facebook_app_secret: str | None = Field(
        default=None,
        description="Facebook App secret (optional, for signature verification)",
    )

    # Supabase Configuration
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_service_key: str = Field(..., description="Supabase service role key")
    # Postgres connection string for running migrations (Supabase Dashboard → Database → Connection string)
    database_url: str | None = Field(
        default=None,
        description="Postgres URI for migrations (e.g. postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres)",
    )

    # PydanticAI Gateway Configuration
    pydantic_ai_gateway_api_key: str = Field(
        ..., description="PydanticAI Gateway API key (paig_xxx)"
    )
    default_model: str = Field(
        default="gateway/anthropic:claude-3-5-sonnet-latest",
        description="Default LLM model to use via PAIG (Anthropic only)",
    )
    fallback_model: str = Field(
        default="gateway/anthropic:claude-3-5-haiku-latest",
        description="Fallback Anthropic model if primary fails",
    )

    # Embedding (via PydanticAI Gateway)
    embedding_model: str = Field(
        default="gateway/openai:text-embedding-3-small",
        description="Embedding model via PAIG (e.g. gateway/openai:text-embedding-3-small)",
    )
    embedding_dimensions: int = Field(
        default=DEFAULT_EMBEDDING_DIMENSIONS,
        description="Embedding vector dimension (matches text-embedding-3-small)",
    )
    search_result_limit: int = Field(
        default=DEFAULT_SEARCH_RESULT_LIMIT,
        description="Max number of chunks to return from page search",
    )

    # OpenAI Configuration (kept for direct fallback if needed)
    openai_api_key: str = Field(
        default="", description="OpenAI API key (legacy fallback)"
    )

    # Environment
    env: Literal["local", "railway", "prod"] = Field(
        default="local", description="Current environment"
    )

    # Sentry Configuration
    sentry_dsn: str | None = Field(
        default=None, description="Sentry DSN for error tracking (optional)"
    )
    sentry_traces_sample_rate: float = Field(
        default=1.0, description="Sentry traces sample rate (0.0 to 1.0)"
    )

    # Logfire Configuration (NEW - pairs with PAIG)
    logfire_token: str | None = Field(
        default=None, description="Pydantic Logfire token for AI observability"
    )

    # ==========================================================================
    # Timeout Configuration
    # ==========================================================================
    # All timeouts can be overridden via environment variables.
    # Defaults are sourced from src/constants.py.

    scraper_timeout_seconds: float = Field(
        default=DEFAULT_HTTP_TIMEOUT_SECONDS,
        description="HTTP timeout for scraper requests (seconds)",
    )
    facebook_api_timeout_seconds: float = Field(
        default=FACEBOOK_API_TIMEOUT_SECONDS,
        description="Timeout for Facebook Graph API calls (seconds)",
    )
    browser_page_load_timeout_seconds: float = Field(
        default=BROWSER_PAGE_LOAD_TIMEOUT_SECONDS,
        description="Timeout for browser page loads (seconds)",
    )
    browser_js_refetch_timeout_seconds: float = Field(
        default=BROWSER_JS_REFETCH_TIMEOUT_SECONDS,
        description="Extended timeout for JS-rendered page refetch (seconds)",
    )

    # ==========================================================================
    # Rate Limiting Configuration (from GUARDRAILS.md)
    # ==========================================================================

    rate_limit_max_messages: int = Field(
        default=MAX_MESSAGES_PER_USER_PER_MINUTE,
        description="Max messages per user per rate limit window",
    )
    rate_limit_window_seconds: int = Field(
        default=RATE_LIMIT_WINDOW_SECONDS,
        description="Rate limit sliding window duration in seconds",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
