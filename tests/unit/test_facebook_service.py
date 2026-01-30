"""Tests for Facebook service."""

import json
import pytest
from hypothesis import given, strategies as st
import httpx
import respx

from src.services.facebook_service import get_user_info, send_message


class TestSendMessage:
    """Test send_message() function."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_valid_inputs(self):
        """Test send_message() with valid inputs."""
        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        await send_message(
            page_access_token="test-token",
            recipient_id="user-123",
            text="Hello, this is a test message",
        )

        # Verify request was made correctly
        request = respx.calls.last.request
        assert request.method == "POST"
        assert request.url.host == "graph.facebook.com"
        assert request.url.path == "/v18.0/me/messages"

        # Verify query parameters
        assert "access_token" in str(request.url)

        # Verify payload
        import json

        # respx captures request body in request.content as bytes
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["recipient"]["id"] == "user-123"
        assert payload["message"]["text"] == "Hello, this is a test message"

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_request_format(self):
        """Test that request format matches Facebook Graph API requirements."""
        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            return_value=httpx.Response(200, json={"message_id": "msg-123"})
        )

        await send_message(
            page_access_token="token-123",
            recipient_id="recipient-456",
            text="Test message",
        )

        request = respx.calls.last.request
        import json

        payload = json.loads(request.content.decode("utf-8"))

        # Verify structure
        assert "recipient" in payload
        assert "id" in payload["recipient"]
        assert "message" in payload
        assert "text" in payload["message"]

        # Verify values
        assert payload["recipient"]["id"] == "recipient-456"
        assert payload["message"]["text"] == "Test message"

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_invalid_token(self):
        """Test error handling for invalid token."""
        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            return_value=httpx.Response(
                401, json={"error": {"message": "Invalid access token"}}
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await send_message(
                page_access_token="invalid-token",
                recipient_id="user-123",
                text="Test message",
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_network_error(self):
        """Test error handling for network errors."""
        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with pytest.raises(httpx.ConnectError):
            await send_message(
                page_access_token="test-token",
                recipient_id="user-123",
                text="Test message",
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_timeout(self):
        """Test timeout handling."""
        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        with pytest.raises(httpx.TimeoutException):
            await send_message(
                page_access_token="test-token",
                recipient_id="user-123",
                text="Test message",
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_http_error(self):
        """Test error handling for HTTP errors."""
        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            return_value=httpx.Response(
                500, json={"error": {"message": "Internal server error"}}
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await send_message(
                page_access_token="test-token",
                recipient_id="user-123",
                text="Test message",
            )

    @pytest.mark.asyncio
    @given(
        recipient_id=st.text(min_size=1, max_size=100),
        text=st.text(min_size=1, max_size=2000),
    )
    @respx.mock
    async def test_send_message_properties(self, recipient_id: str, text: str):
        """Property: send_message() should handle various inputs."""
        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            return_value=httpx.Response(200, json={"message_id": "msg-123"})
        )

        # Should not raise exception for valid inputs
        await send_message(
            page_access_token="test-token", recipient_id=recipient_id, text=text
        )

        # Verify request was made
        assert len(respx.calls) == 1
        request = respx.calls.last.request
        import json

        payload = json.loads(request.content.decode("utf-8"))
        assert payload["recipient"]["id"] == recipient_id
        assert payload["message"]["text"] == text

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_access_token_in_params(self):
        """Test that access token is passed as query parameter."""
        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            return_value=httpx.Response(200, json={"message_id": "msg-123"})
        )

        await send_message(
            page_access_token="special-token-123", recipient_id="user-123", text="Test"
        )

        request = respx.calls.last.request
        # Access token should be in query params
        assert "access_token" in str(request.url)
        assert "special-token-123" in str(request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_long_text(self):
        """Test sending long messages."""
        long_text = "A" * 5000  # Very long message

        respx.post("https://graph.facebook.com/v18.0/me/messages").mock(
            return_value=httpx.Response(200, json={"message_id": "msg-123"})
        )

        # Should handle long messages (Facebook may truncate, but function should work)
        await send_message(
            page_access_token="test-token", recipient_id="user-123", text=long_text
        )

        request = respx.calls.last.request
        payload = json.loads(request.content.decode("utf-8"))
        assert len(payload["message"]["text"]) == 5000


class TestGetUserInfo:
    """Test get_user_info() function."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_success(self):
        """get_user_info returns FacebookUserInfo on 200."""
        respx.get("https://graph.facebook.com/v18.0/user-123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "user-123",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "picture": {
                        "data": {"url": "https://graph.facebook.com/pic/user-123"}
                    },
                    "locale": "en_US",
                    "timezone": -6,
                },
            )
        )

        out = await get_user_info(
            page_access_token="token", user_id="user-123"
        )
        assert out is not None
        assert out.id == "user-123"
        assert out.first_name == "Jane"
        assert out.last_name == "Doe"
        assert out.profile_pic == "https://graph.facebook.com/pic/user-123"
        assert out.locale == "en_US"
        assert out.timezone == -6

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_no_picture(self):
        """get_user_info handles missing picture."""
        respx.get("https://graph.facebook.com/v18.0/user-456").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "user-456",
                    "first_name": "John",
                    "locale": "en_GB",
                },
            )
        )

        out = await get_user_info(
            page_access_token="token", user_id="user-456"
        )
        assert out is not None
        assert out.first_name == "John"
        assert out.profile_pic is None
        assert out.locale == "en_GB"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_http_error(self):
        """get_user_info returns None on non-200."""
        respx.get("https://graph.facebook.com/v18.0/user-789").mock(
            return_value=httpx.Response(401, json={"error": {"message": "Invalid"}})
        )

        out = await get_user_info(
            page_access_token="bad-token", user_id="user-789"
        )
        assert out is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_user_info_request_format(self):
        """get_user_info requests correct fields and token."""
        respx.get("https://graph.facebook.com/v18.0/psid-1").mock(
            return_value=httpx.Response(
                200,
                json={"id": "psid-1", "first_name": "A"},
            )
        )

        await get_user_info(
            page_access_token="my-page-token", user_id="psid-1"
        )

        req = respx.calls.last.request
        assert "access_token" in str(req.url)
        assert "my-page-token" in str(req.url)
        assert "first_name" in str(req.url)
        assert "last_name" in str(req.url)
        assert "picture" in str(req.url)
        assert "locale" in str(req.url)
        assert "timezone" in str(req.url)
