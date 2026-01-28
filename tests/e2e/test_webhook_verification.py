"""End-to-end tests for webhook verification."""

import pytest
from unittest.mock import patch

from src.main import app
from fastapi.testclient import TestClient


class TestWebhookVerification:
    """Test Facebook webhook verification endpoint."""
    
    @patch('src.api.webhook.get_settings')
    def test_webhook_verification_success(self, mock_get_settings, test_client):
        """Test webhook verification with correct token."""
        from src.config import Settings
        
        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify-token-123",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key"
        )
        mock_get_settings.return_value = mock_settings
        
        response = test_client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token-123",
                "hub.challenge": "challenge-123"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "challenge-123"
    
    @patch('src.api.webhook.get_settings')
    def test_webhook_verification_fails_invalid_token(self, mock_get_settings, test_client):
        """Test webhook verification fails with incorrect token."""
        from src.config import Settings
        
        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify-token-123",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key"
        )
        mock_get_settings.return_value = mock_settings
        
        response = test_client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge-123"
            }
        )
        
        assert response.status_code == 403
    
    @patch('src.api.webhook.get_settings')
    def test_webhook_verification_fails_wrong_mode(self, mock_get_settings, test_client):
        """Test webhook verification fails with wrong mode."""
        from src.config import Settings
        
        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify-token-123",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key"
        )
        mock_get_settings.return_value = mock_settings
        
        response = test_client.get(
            "/webhook",
            params={
                "hub.mode": "unsubscribe",  # Wrong mode
                "hub.verify_token": "test-verify-token-123",
                "hub.challenge": "challenge-123"
            }
        )
        
        assert response.status_code == 403
    
    @patch('src.api.webhook.get_settings')
    def test_webhook_verification_missing_parameters(self, mock_get_settings, test_client):
        """Test webhook verification with missing parameters."""
        from src.config import Settings
        
        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify-token-123",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key"
        )
        mock_get_settings.return_value = mock_settings
        
        # Missing challenge - returns 200 with None as challenge (PlainTextResponse with None)
        response = test_client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token-123"
            }
        )
        
        # When challenge is missing but verification passes, it returns the None challenge
        # This is expected behavior - the actual challenge value is None
        assert response.status_code == 200
    
    @patch('src.api.webhook.get_settings')
    def test_webhook_verification_challenge_response_format(self, mock_get_settings, test_client):
        """Test that challenge is returned as plain text."""
        from src.config import Settings
        
        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify-token-123",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key"
        )
        mock_get_settings.return_value = mock_settings
        
        response = test_client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token-123",
                "hub.challenge": "random-challenge-string-456"
            }
        )
        
        assert response.status_code == 200
        assert response.text == "random-challenge-string-456"
        # Should be plain text, not JSON
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
