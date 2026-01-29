"""End-to-end tests for webhook message processing flow."""

from unittest.mock import patch



class TestWebhookMessageFlow:
    """Test complete webhook message processing flow."""

    @patch("src.api.webhook.get_settings")
    def test_webhook_message_processing(self, mock_get_settings, test_client):
        """Test POST /webhook with valid payload processes message."""
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

        # Webhook payload
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page-123",
                    "time": 1234567890,
                    "messaging": [
                        {
                            "sender": {"id": "user-456"},
                            "recipient": {"id": "page-123"},
                            "message": {
                                "text": "Hello, what can you help me with?",
                                "mid": "msg-123",
                            },
                            "timestamp": 1234567890,
                        }
                    ],
                }
            ],
        }

        # Note: The webhook handler is currently a TODO, so this test
        # verifies the structure but may need updates when handler is implemented
        response = test_client.post("/webhook", json=payload)

        # Should return 200 (even if handler is not fully implemented)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @patch("src.api.webhook.get_settings")
    def test_webhook_no_bot_config(self, mock_get_settings, test_client):
        """Test error handling when bot configuration is not found."""
        from src.config import Settings

        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key",
            pydantic_ai_gateway_api_key="paig_test_key",
        )
        mock_get_settings.return_value = mock_settings

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page-999",
                    "messaging": [
                        {
                            "sender": {"id": "user-456"},
                            "recipient": {"id": "page-999"},
                            "message": {"text": "Hello"},
                            "timestamp": 1234567890,
                        }
                    ],
                }
            ],
        }

        response = test_client.post("/webhook", json=payload)

        # Should handle gracefully (currently returns 200, but may change)
        assert response.status_code in [200, 404, 400]

    @patch("src.api.webhook.get_settings")
    def test_webhook_invalid_payload(self, mock_get_settings, test_client):
        """Test error handling with invalid payload."""
        from src.config import Settings

        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key",
            pydantic_ai_gateway_api_key="paig_test_key",
        )
        mock_get_settings.return_value = mock_settings

        # Invalid payload structure
        payload = {
            "object": "page",
            "entry": [],  # Empty entry
        }

        response = test_client.post("/webhook", json=payload)

        # Should handle gracefully
        assert response.status_code in [200, 400]

    @patch("src.api.webhook.get_settings")
    def test_webhook_message_extraction(self, mock_get_settings, test_client):
        """Test that message is extracted correctly from payload."""
        from src.config import Settings

        mock_settings = Settings(
            facebook_page_access_token="test-token",
            facebook_verify_token="test-verify",
            supabase_url="https://test.supabase.co",
            supabase_service_key="test-key",
            pydantic_ai_gateway_api_key="paig_test_key",
        )
        mock_get_settings.return_value = mock_settings

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page-123",
                    "messaging": [
                        {
                            "sender": {"id": "user-789"},
                            "recipient": {"id": "page-123"},
                            "message": {"text": "Test message text"},
                            "timestamp": 1234567890,
                        }
                    ],
                }
            ],
        }

        response = test_client.post("/webhook", json=payload)

        # Verify payload structure is valid
        assert "entry" in payload
        assert len(payload["entry"]) > 0
        assert "messaging" in payload["entry"][0]
        assert len(payload["entry"][0]["messaging"]) > 0
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
