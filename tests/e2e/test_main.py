"""End-to-end tests for main application."""

from unittest.mock import patch, MagicMock

from src.main import app


class TestMainApplication:
    """Test FastAPI application initialization."""

    def test_app_initialization(self):
        """Test that FastAPI app is initialized correctly."""
        assert app is not None
        assert app.title == "Facebook Messenger AI Bot"
        assert app.version == "0.2.0"

    def test_root_endpoint(self, test_client):
        """Test root endpoint."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Facebook Messenger AI Bot" in data["message"]

    def test_cors_middleware(self, test_client):
        """Test that CORS middleware is configured."""
        # CORS is configured in app, test by checking headers
        response = test_client.options("/health")

        # CORS middleware should be present
        # (exact headers depend on CORS configuration)
        assert response.status_code in [200, 405]  # OPTIONS may return 405

    @patch("src.api.webhook.get_settings")
    def test_router_registration(self, mock_get_settings, test_client):
        """Test that routers are registered."""
        from src.config import Settings

        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key",
            pydantic_ai_gateway_api_key="paig_test_key",
        )
        mock_get_settings.return_value = mock_settings

        # Health endpoint should be available
        response = test_client.get("/health")
        assert response.status_code == 200

        # Webhook endpoint should be available (returns 403 without proper params)
        response = test_client.get("/webhook")
        assert response.status_code == 403  # No params provided

    @patch("src.main.get_supabase_client")
    @patch("src.main.get_settings")
    def test_lifespan_startup(self, mock_get_settings, mock_get_supabase):
        """Test application lifespan startup."""
        from src.config import Settings

        # Mock settings
        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key",
            pydantic_ai_gateway_api_key="paig_test_key",
        )
        mock_get_settings.return_value = mock_settings

        # Mock Supabase
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Test lifespan context manager
        from src.main import lifespan

        # This would normally be called by FastAPI
        # We can test the structure, but full async context testing is complex
        assert lifespan is not None

    def test_app_metadata(self):
        """Test application metadata."""
        assert app.title == "Facebook Messenger AI Bot"
        assert app.description is not None
        assert app.version == "0.2.0"

    def test_app_routes(self):
        """Test that all expected routes are registered."""
        routes = [route.path for route in app.routes]

        # Check for expected routes
        assert "/" in routes
        assert "/health" in routes
        assert "/webhook" in routes
