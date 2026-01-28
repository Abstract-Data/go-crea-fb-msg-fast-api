"""Tests for Copilot service."""

import pytest
from unittest.mock import AsyncMock, patch
import httpx
import respx

from src.services.copilot_service import CopilotService


class TestCopilotService:
    """Test CopilotService class."""
    
    def test_init(self):
        """Test CopilotService initialization."""
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        assert copilot.base_url == "http://localhost:5909"
        assert copilot.enabled is True
    
    def test_init_strips_trailing_slash(self):
        """Test that base_url trailing slash is stripped."""
        copilot = CopilotService(base_url="http://localhost:5909/", enabled=True)
        assert copilot.base_url == "http://localhost:5909"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_is_available_when_available(self):
        """Test is_available() when Copilot is available."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        result = await copilot.is_available()
        
        assert result is True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_is_available_when_unavailable(self):
        """Test is_available() when Copilot is unavailable."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(500))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        result = await copilot.is_available()
        
        assert result is False
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_is_available_when_connection_error(self):
        """Test is_available() when connection fails."""
        respx.get("http://localhost:5909/health").mock(side_effect=httpx.ConnectError("Connection failed"))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        result = await copilot.is_available()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_is_available_when_disabled(self):
        """Test is_available() when Copilot is disabled."""
        copilot = CopilotService(base_url="http://localhost:5909", enabled=False)
        result = await copilot.is_available()
        
        assert result is False
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_is_available_timeout(self):
        """Test is_available() timeout handling."""
        respx.get("http://localhost:5909/health").mock(side_effect=httpx.TimeoutException("Timeout"))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        result = await copilot.is_available()
        
        assert result is False
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_synthesize_reference(self):
        """Test synthesize_reference() with mocked Copilot response."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(return_value=httpx.Response(
            200,
            json={"content": "# Reference Document\n\nTest content"}
        ))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        result = await copilot.synthesize_reference(
            website_url="https://example.com",
            text_chunks=["chunk1", "chunk2"]
        )
        
        assert isinstance(result, str)
        assert "Reference Document" in result
        
        # Verify request was made correctly
        request = respx.calls.last.request
        assert request.method == "POST"
        assert request.url.path == "/chat"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_with_available_copilot(self):
        """Test chat() when Copilot is available."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(return_value=httpx.Response(
            200,
            json={"content": "Test response"}
        ))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        result = await copilot.chat(
            system_prompt="You are a helpful assistant",
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        assert result == "Test response"
        
        # Verify request format
        request = respx.calls.last.request
        assert request.method == "POST"
        json_data = request.read()
        assert b"system_prompt" in json_data
        assert b"messages" in json_data
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_fallback_when_unavailable(self):
        """Test chat() falls back to OpenAI when Copilot unavailable."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(500))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        
        # Mock the fallback method
        with patch.object(copilot, '_fallback_to_openai', new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = "Fallback response"
            
            result = await copilot.chat(
                system_prompt="You are a helpful assistant",
                messages=[{"role": "user", "content": "Hello"}]
            )
            
            assert result == "Fallback response"
            mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_fallback_on_error(self):
        """Test chat() falls back to OpenAI on error."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(side_effect=httpx.HTTPError("Error"))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        
        # Mock the fallback method
        with patch.object(copilot, '_fallback_to_openai', new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = "Fallback response"
            
            result = await copilot.chat(
                system_prompt="You are a helpful assistant",
                messages=[{"role": "user", "content": "Hello"}]
            )
            
            assert result == "Fallback response"
            mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_chat_timeout_handling(self):
        """Test chat() timeout handling."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(side_effect=httpx.TimeoutException("Timeout"))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        
        # Mock the fallback method
        with patch.object(copilot, '_fallback_to_openai', new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = "Fallback response"
            
            result = await copilot.chat(
                system_prompt="You are a helpful assistant",
                messages=[{"role": "user", "content": "Hello"}]
            )
            
            assert result == "Fallback response"
            mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_chat_when_disabled(self):
        """Test chat() when Copilot is disabled."""
        copilot = CopilotService(base_url="http://localhost:5909", enabled=False)
        
        # Mock the fallback method
        with patch.object(copilot, '_fallback_to_openai', new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = "Fallback response"
            
            result = await copilot.chat(
                system_prompt="You are a helpful assistant",
                messages=[{"role": "user", "content": "Hello"}]
            )
            
            assert result == "Fallback response"
            mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fallback_to_openai_not_implemented(self):
        """Test that _fallback_to_openai raises NotImplementedError."""
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        
        with pytest.raises(NotImplementedError, match="OpenAI fallback not yet implemented"):
            await copilot._fallback_to_openai(
                system_prompt="Test",
                messages=[{"role": "user", "content": "Hello"}]
            )
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_synthesize_reference_builds_correct_prompt(self):
        """Test that synthesize_reference() builds correct prompt."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(return_value=httpx.Response(
            200,
            json={"content": "# Reference Document"}
        ))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        await copilot.synthesize_reference(
            website_url="https://example.com",
            text_chunks=["chunk1", "chunk2", "chunk3"]
        )
        
        # Verify the request includes website URL and chunks
        request = respx.calls.last.request
        json_data = request.read().decode()
        assert "example.com" in json_data
        assert "chunk1" in json_data
        assert "chunk2" in json_data
        assert "chunk3" in json_data
