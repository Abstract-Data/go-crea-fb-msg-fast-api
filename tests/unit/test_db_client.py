"""Tests for database client."""

from unittest.mock import patch, MagicMock

from src.db.client import get_supabase_client
from src.config import Settings


class TestGetSupabaseClient:
    """Test get_supabase_client() function."""

    @patch("src.db.client.create_client")
    @patch("src.db.client.get_settings")
    def test_get_supabase_client_initialization(
        self, mock_get_settings, mock_create_client
    ):
        """Test get_supabase_client() initialization."""
        # Mock settings
        mock_settings = MagicMock(spec=Settings)
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_key = "test-service-key"
        mock_get_settings.return_value = mock_settings

        # Mock Supabase client
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Call function
        client = get_supabase_client()

        # Verify client was created with correct parameters
        mock_create_client.assert_called_once_with(
            "https://test.supabase.co", "test-service-key"
        )
        assert client is mock_client

    @patch("src.db.client.create_client")
    @patch("src.db.client.get_settings")
    def test_get_supabase_client_uses_settings(
        self, mock_get_settings, mock_create_client
    ):
        """Test that get_supabase_client() uses settings from get_settings()."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.supabase_url = "https://custom.supabase.co"
        mock_settings.supabase_service_key = "custom-key"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        get_supabase_client()

        # Verify settings were used
        mock_create_client.assert_called_once_with(
            "https://custom.supabase.co", "custom-key"
        )
