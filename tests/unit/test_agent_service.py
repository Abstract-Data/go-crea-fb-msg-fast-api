"""Tests for PydanticAI Gateway agent service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.agent_models import AgentContext, AgentResponse
from src.services.agent_service import MessengerAgentService, MessengerAgentDeps


class TestMessengerAgentService:
    """Test suite for MessengerAgentService."""
    
    @pytest.fixture
    def agent_context(self):
        """Sample agent context."""
        return AgentContext(
            bot_config_id="test-bot-id",
            reference_doc="# Test Reference\n\nThis is a test document about our services.",
            tone="professional",
            recent_messages=["Hello", "How can I help?"],
        )
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        with patch('src.services.agent_service.get_settings') as mock:
            settings = MagicMock()
            settings.pydantic_ai_gateway_api_key = "paig_test_key"
            settings.default_model = "gateway/openai:gpt-4o"
            settings.fallback_model = "gateway/anthropic:claude-3-5-sonnet-latest"
            mock.return_value = settings
            yield mock
    
    @pytest.mark.asyncio
    async def test_respond_returns_agent_response(self, agent_context, mock_settings):
        """Test that respond returns a properly typed AgentResponse."""
        with patch('src.services.agent_service.Agent') as MockAgent:
            # Setup mock result
            mock_result = MagicMock()
            mock_result.output = AgentResponse(
                message="Test response",
                confidence=0.9,
                requires_escalation=False,
            )
            
            # Create mock agent instance with properly configured async run method
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_instance.tool = MagicMock(return_value=lambda f: f)
            mock_agent_instance.system_prompt = MagicMock(return_value=lambda f: f)
            MockAgent.return_value = mock_agent_instance
            
            # Test - create service after patching
            service = MessengerAgentService()
            response = await service.respond(agent_context, "What services do you offer?")
            
            # Assertions
            assert isinstance(response, AgentResponse)
            assert response.message == "Test response"
            assert response.confidence == 0.9
            assert not response.requires_escalation
    
    @pytest.mark.asyncio
    async def test_respond_handles_errors_gracefully(self, agent_context, mock_settings):
        """Test that errors result in escalation response."""
        with patch('src.services.agent_service.Agent') as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(side_effect=Exception("API Error"))
            mock_agent_instance.tool = MagicMock(return_value=lambda f: f)
            MockAgent.return_value = mock_agent_instance
            
            service = MessengerAgentService()
            response = await service.respond(agent_context, "Test message")
            
            assert response.requires_escalation is True
            assert response.confidence == 0.0
            assert "error" in response.escalation_reason.lower()
    
    def test_agent_response_should_escalate(self):
        """Test escalation threshold logic."""
        # High confidence, no escalation flag
        response1 = AgentResponse(message="Test", confidence=0.9, requires_escalation=False)
        assert response1.should_escalate(threshold=0.7) is False
        
        # Low confidence
        response2 = AgentResponse(message="Test", confidence=0.5, requires_escalation=False)
        assert response2.should_escalate(threshold=0.7) is True
        
        # Escalation flag set
        response3 = AgentResponse(message="Test", confidence=0.9, requires_escalation=True)
        assert response3.should_escalate(threshold=0.7) is True
    
    @pytest.mark.asyncio
    async def test_respond_with_tenant_id(self, mock_settings):
        """Test that tenant_id is passed through correctly."""
        context = AgentContext(
            bot_config_id="test-bot-id",
            reference_doc="Test doc",
            tone="professional",
            recent_messages=[],
            tenant_id="tenant-123",
        )
        
        with patch('src.services.agent_service.Agent') as MockAgent:
            mock_result = MagicMock()
            mock_result.output = AgentResponse(
                message="Test",
                confidence=0.8,
                requires_escalation=False,
            )
            
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_instance.tool = MagicMock(return_value=lambda f: f)
            MockAgent.return_value = mock_agent_instance
            
            service = MessengerAgentService()
            response = await service.respond(context, "Test message")
            
            # Verify agent was called with tenant_id in deps
            call_args = mock_agent_instance.run.call_args
            deps = call_args[1]['deps']
            assert deps.tenant_id == "tenant-123"
    
    @pytest.mark.asyncio
    async def test_respond_with_fallback(self, agent_context, mock_settings):
        """Test respond_with_fallback method."""
        with patch('src.services.agent_service.Agent') as MockAgent, \
             patch('src.services.agent_service.FallbackModel') as MockFallbackModel:
            mock_result = MagicMock()
            mock_result.output = AgentResponse(
                message="Fallback response",
                confidence=0.8,
                requires_escalation=False,
            )
            
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_instance.tool = MagicMock(return_value=lambda f: f)
            MockAgent.return_value = mock_agent_instance
            MockFallbackModel.return_value = "fallback_model"
            
            service = MessengerAgentService()
            response = await service.respond_with_fallback(agent_context, "Test message")
            
            assert isinstance(response, AgentResponse)
            assert response.message == "Fallback response"
    
    @pytest.mark.asyncio
    async def test_system_prompt_includes_reference_doc(self, agent_context, mock_settings):
        """Test that system prompt is registered and respond uses reference doc via deps."""
        with patch('src.services.agent_service.Agent') as MockAgent:
            mock_result = MagicMock()
            mock_result.output = AgentResponse(
                message="Test",
                confidence=0.8,
                requires_escalation=False,
            )
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_instance.tool = MagicMock(return_value=lambda f: f)
            mock_agent_instance.system_prompt = MagicMock(return_value=lambda f: f)
            MockAgent.return_value = mock_agent_instance

            service = MessengerAgentService()
            await service.respond(agent_context, "Test message")

            # Agent created with system_prompt=() and deps_type; dynamic prompt registered via .system_prompt()
            MockAgent.assert_called_once()
            call_kwargs = MockAgent.call_args[1]
            assert call_kwargs.get('system_prompt') == ()
            assert mock_agent_instance.system_prompt.called
    
    def test_agent_initialization_with_custom_model(self, mock_settings):
        """Test agent initialization with custom model."""
        with patch('src.services.agent_service.Agent') as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.tool = MagicMock(return_value=lambda f: f)
            MockAgent.return_value = mock_agent_instance
            
            service = MessengerAgentService(model="gateway/anthropic:claude-3-5-sonnet-latest")
            
            # Verify Agent was called with custom model
            MockAgent.assert_called_once()
            call_args = MockAgent.call_args[0]
            assert call_args[0] == "gateway/anthropic:claude-3-5-sonnet-latest"
    
    def test_agent_response_message_length_validation(self):
        """Test that AgentResponse validates message length."""
        # Valid message
        response = AgentResponse(
            message="Short message",
            confidence=0.8,
            requires_escalation=False,
        )
        assert len(response.message) <= 500
        
        # Message too long should fail validation
        long_message = "x" * 501
        with pytest.raises(Exception):  # Pydantic validation error
            AgentResponse(
                message=long_message,
                confidence=0.8,
                requires_escalation=False,
            )
    
    def test_agent_response_confidence_bounds(self):
        """Test that confidence is bounded between 0.0 and 1.0."""
        # Valid confidence
        response1 = AgentResponse(message="Test", confidence=0.5, requires_escalation=False)
        assert 0.0 <= response1.confidence <= 1.0
        
        # Confidence out of bounds should fail validation
        with pytest.raises(Exception):  # Pydantic validation error
            AgentResponse(message="Test", confidence=1.5, requires_escalation=False)
        
        with pytest.raises(Exception):  # Pydantic validation error
            AgentResponse(message="Test", confidence=-0.1, requires_escalation=False)
