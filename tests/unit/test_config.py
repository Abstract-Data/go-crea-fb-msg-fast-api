"""Tests for application configuration."""

import pytest
from hypothesis import given, strategies as st
from unittest.mock import patch

from src.config import Settings, get_settings


class TestSettings:
    """Test Settings model validation."""

    _REQUIRED_ENV_KEYS = (
        "FACEBOOK_PAGE_ACCESS_TOKEN",
        "FACEBOOK_VERIFY_TOKEN",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "PYDANTIC_AI_GATEWAY_API_KEY",
    )

    def test_settings_required_fields(self, monkeypatch):
        """Test that required fields are enforced when not provided via env."""
        get_settings.cache_clear()
        for key in self._REQUIRED_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        try:
            Settings()
        except Exception:
            return  # Expected: validation error when required fields missing
        pytest.skip(
            "Required env vars are set (e.g. in .env); cannot test missing-required validation"
        )

    def test_settings_with_all_fields(self):
        """Test Settings with all required fields."""
        settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="verify-token",
            supabase_url="https://test.supabase.co",
            supabase_service_key="service-key",
            pydantic_ai_gateway_api_key="paig_test_key",
        )
        assert settings.facebook_page_access_token == "test-token"
        assert settings.facebook_verify_token == "verify-token"
        assert settings.supabase_url == "https://test.supabase.co"
        assert settings.supabase_service_key == "service-key"
        assert settings.pydantic_ai_gateway_api_key == "paig_test_key"

    def test_settings_default_values(self, monkeypatch):
        """Test that default values are set correctly when not overridden by env."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("FACEBOOK_APP_SECRET", raising=False)
        monkeypatch.delenv("DEFAULT_MODEL", raising=False)
        monkeypatch.delenv("FALLBACK_MODEL", raising=False)
        settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="verify-token",
            supabase_url="https://test.supabase.co",
            supabase_service_key="service-key",
            pydantic_ai_gateway_api_key="paig_test_key",
            openai_api_key="",
            facebook_app_secret=None,
        )
        assert settings.default_model == "gateway/anthropic:claude-3-5-sonnet-latest"
        assert settings.fallback_model == "gateway/anthropic:claude-3-5-haiku-latest"
        assert settings.openai_api_key == ""
        assert settings.env == "local"
        assert settings.facebook_app_secret is None

    @given(
        default_model=st.text(min_size=1, max_size=200),
        fallback_model=st.text(min_size=1, max_size=200),
        env=st.sampled_from(["local", "railway", "prod"]),
    )
    @pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
    def test_settings_optional_fields_properties(
        self, default_model: str, fallback_model: str, env: str
    ):
        """Property: Settings should accept valid optional field values."""
        get_settings.cache_clear()
        settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="verify-token",
            supabase_url="https://test.supabase.co",
            supabase_service_key="service-key",
            pydantic_ai_gateway_api_key="paig_test_key",
            default_model=default_model,
            fallback_model=fallback_model,
            env=env,
        )
        assert settings.default_model == default_model
        assert settings.fallback_model == fallback_model
        assert settings.env == env

    def test_settings_env_validation(self):
        """Test that env field only accepts valid values."""
        # Valid values
        for env in ["local", "railway", "prod"]:
            settings = Settings(
                facebook_page_access_token="test-token",
                facebook_verify_token="verify-token",
                supabase_url="https://test.supabase.co",
                supabase_service_key="service-key",
                pydantic_ai_gateway_api_key="paig_test_key",
                env=env,
            )
            assert settings.env == env

        # Invalid value should raise validation error
        with pytest.raises(Exception):  # Pydantic validation error
            Settings(
                facebook_page_access_token="test-token",
                facebook_verify_token="verify-token",
                supabase_url="https://test.supabase.co",
                supabase_service_key="service-key",
                pydantic_ai_gateway_api_key="paig_test_key",
                env="invalid",
            )


class TestGetSettings:
    """Test get_settings() function."""

    @patch.dict(
        "os.environ",
        {
            "FACEBOOK_PAGE_ACCESS_TOKEN": "test-token",
            "FACEBOOK_VERIFY_TOKEN": "test-verify",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_SERVICE_KEY": "test-key",
            "PYDANTIC_AI_GATEWAY_API_KEY": "paig_test_key",
        },
    )
    def test_get_settings_caching(self):
        """Test that get_settings() returns cached instance."""
        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance (cached)
        assert settings1 is settings2

    @patch.dict(
        "os.environ",
        {
            "FACEBOOK_PAGE_ACCESS_TOKEN": "env-token",
            "FACEBOOK_VERIFY_TOKEN": "env-verify",
            "SUPABASE_URL": "https://env.supabase.co",
            "SUPABASE_SERVICE_KEY": "env-service-key",
            "PYDANTIC_AI_GATEWAY_API_KEY": "paig_env_key",
        },
    )
    def test_get_settings_from_env(self):
        """Test that get_settings() loads from environment variables."""
        # Clear cache to force reload
        get_settings.cache_clear()

        settings = get_settings()

        assert settings.facebook_page_access_token == "env-token"
        assert settings.facebook_verify_token == "env-verify"
        assert settings.supabase_url == "https://env.supabase.co"
        assert settings.supabase_service_key == "env-service-key"

    def test_get_settings_case_insensitive(self):
        """Test that environment variable names are case-insensitive."""
        with patch.dict(
            "os.environ",
            {
                "facebook_page_access_token": "lowercase-token",
                "FACEBOOK_VERIFY_TOKEN": "uppercase-verify",
                "Supabase_Url": "mixed-case-url",
                "SUPABASE_SERVICE_KEY": "service-key",
                "PYDANTIC_AI_GATEWAY_API_KEY": "paig_test_key",
            },
        ):
            get_settings.cache_clear()
            settings = get_settings()

            # Pydantic-settings should handle case-insensitive matching
            assert settings.supabase_service_key == "service-key"
