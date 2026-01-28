"""Application configuration using Pydantic BaseSettings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Facebook Configuration
    facebook_page_access_token: str = Field(
        ...,
        description="Facebook Page access token"
    )
    facebook_verify_token: str = Field(
        ...,
        description="Webhook verification token"
    )
    facebook_app_secret: str | None = Field(
        default=None,
        description="Facebook App secret (optional, for signature verification)"
    )
    
    # Supabase Configuration
    supabase_url: str = Field(
        ...,
        description="Supabase project URL"
    )
    supabase_service_key: str = Field(
        ...,
        description="Supabase service role key"
    )
    
    # Copilot SDK Configuration
    copilot_cli_host: str = Field(
        default="http://localhost:5909",
        description="GitHub Copilot CLI host URL"
    )
    copilot_enabled: bool = Field(
        default=True,
        description="Enable Copilot SDK (False to use OpenAI fallback)"
    )
    
    # OpenAI Configuration (Fallback)
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (used as fallback)"
    )
    
    # Environment
    env: Literal["local", "railway", "prod"] = Field(
        default="local",
        description="Current environment"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
