"""Application configuration using Pydantic BaseSettings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
