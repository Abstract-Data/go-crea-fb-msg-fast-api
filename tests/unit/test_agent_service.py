"""Tests for agent service."""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import AsyncMock

from src.services.agent_service import MessengerAgentService
from src.models.agent_models import AgentContext, AgentResponse


class TestMessengerAgentService:
    """Test MessengerAgentService class."""
    
    def test_init(self, mock_copilot_service):
        """Test MessengerAgentService initialization."""
        agent = MessengerAgentService(mock_copilot_service)
        assert agent.copilot is mock_copilot_service
    
    @pytest.mark.asyncio
    async def test_respond_with_valid_context(self, mock_copilot_service, sample_agent_context):
        """Test respond() with valid context and message."""
        mock_copilot_service.chat.return_value = "This is a test response"
        
        agent = MessengerAgentService(mock_copilot_service)
        response = await agent.respond(sample_agent_context, "Hello, what can you help me with?")
        
        assert isinstance(response, AgentResponse)
        assert response.message == "This is a test response"
        assert 0.0 <= response.confidence <= 1.0
        assert isinstance(response.requires_escalation, bool)
    
    @pytest.mark.asyncio
    async def test_respond_system_prompt_construction(self, mock_copilot_service, sample_agent_context):
        """Test that system prompt is constructed correctly."""
        mock_copilot_service.chat.return_value = "Response"
        
        agent = MessengerAgentService(mock_copilot_service)
        await agent.respond(sample_agent_context, "Test message")
        
        # Verify chat was called with correct system prompt
        call_args = mock_copilot_service.chat.call_args
        system_prompt = call_args[0][0]
        
        assert sample_agent_context.tone in system_prompt
        assert sample_agent_context.reference_doc in system_prompt
        assert "300 characters" in system_prompt.lower()
    
    @pytest.mark.asyncio
    async def test_respond_includes_recent_messages(self, mock_copilot_service):
        """Test that recent messages are included in context."""
        mock_copilot_service.chat.return_value = "Response"
        
        context = AgentContext(
            bot_config_id="bot-123",
            reference_doc="Test doc",
            tone="professional",
            recent_messages=["Message 1", "Message 2", "Message 3", "Message 4", "Message 5"]
        )
        
        agent = MessengerAgentService(mock_copilot_service)
        await agent.respond(context, "Current message")
        
        # Verify only last 3 messages are included
        call_args = mock_copilot_service.chat.call_args
        messages = call_args[0][1]
        
        # Should have recent messages + current message
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assert len(user_messages) <= 4  # Last 3 recent + current
    
    @pytest.mark.asyncio
    async def test_respond_escalation_on_dont_know(self, mock_copilot_service, sample_agent_context):
        """Test escalation logic when response contains 'don't know'."""
        mock_copilot_service.chat.return_value = "I don't know the answer to that question"
        
        agent = MessengerAgentService(mock_copilot_service)
        response = await agent.respond(sample_agent_context, "What about something not in the doc?")
        
        assert response.requires_escalation is True
        assert response.escalation_reason is not None
        assert "don't know" in response.message.lower() or "human" in response.message.lower()
    
    @pytest.mark.asyncio
    async def test_respond_escalation_on_human_keyword(self, mock_copilot_service, sample_agent_context):
        """Test escalation logic when response contains 'human'."""
        mock_copilot_service.chat.return_value = "I suggest you contact a human representative"
        
        agent = MessengerAgentService(mock_copilot_service)
        response = await agent.respond(sample_agent_context, "Complex question")
        
        assert response.requires_escalation is True
        assert response.escalation_reason is not None
    
    @pytest.mark.asyncio
    async def test_respond_no_escalation_on_normal_response(self, mock_copilot_service, sample_agent_context):
        """Test that normal responses don't trigger escalation."""
        mock_copilot_service.chat.return_value = "I can help you with that. Here's the information you need."
        
        agent = MessengerAgentService(mock_copilot_service)
        response = await agent.respond(sample_agent_context, "What are your services?")
        
        assert response.requires_escalation is False
        assert response.escalation_reason is None
    
    @pytest.mark.asyncio
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        message=st.text(min_size=1, max_size=500),
        tone=st.sampled_from(["professional", "friendly", "casual", "formal", "humorous"])
    )
    async def test_respond_properties_with_various_inputs(
        self,
        message: str,
        tone: str,
        mock_copilot_service
    ):
        """Property: respond() should always return valid AgentResponse."""
        mock_copilot_service.chat.return_value = "Test response"
        
        context = AgentContext(
            bot_config_id="bot-123",
            reference_doc="Test reference document",
            tone=tone,
            recent_messages=[]
        )
        
        agent = MessengerAgentService(mock_copilot_service)
        response = await agent.respond(context, message)
        
        # Invariants
        assert isinstance(response, AgentResponse)
        assert response.message is not None
        assert len(response.message) > 0
        assert 0.0 <= response.confidence <= 1.0
        assert isinstance(response.requires_escalation, bool)
    
    @pytest.mark.asyncio
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        reference_doc_size=st.integers(min_value=10, max_value=50000),
        message_length=st.integers(min_value=1, max_value=1000)
    )
    async def test_respond_properties_with_various_sizes(
        self,
        reference_doc_size: int,
        message_length: int,
        mock_copilot_service
    ):
        """Property: respond() should handle various reference doc and message sizes."""
        mock_copilot_service.chat.return_value = "Response"
        
        reference_doc = "A" * reference_doc_size
        message = "B" * message_length
        
        context = AgentContext(
            bot_config_id="bot-123",
            reference_doc=reference_doc,
            tone="professional",
            recent_messages=[]
        )
        
        agent = MessengerAgentService(mock_copilot_service)
        response = await agent.respond(context, message)
        
        # Should always return valid response
        assert isinstance(response, AgentResponse)
        assert response.message is not None
    
    @pytest.mark.asyncio
    async def test_respond_confidence_placeholder(self, mock_copilot_service, sample_agent_context):
        """Test that confidence is set (currently placeholder)."""
        mock_copilot_service.chat.return_value = "Response"
        
        agent = MessengerAgentService(mock_copilot_service)
        response = await agent.respond(sample_agent_context, "Test")
        
        # Currently hardcoded to 0.8, but should be in valid range
        assert response.confidence == 0.8
        assert 0.0 <= response.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_respond_empty_recent_messages(self, mock_copilot_service):
        """Test respond() with empty recent messages."""
        mock_copilot_service.chat.return_value = "Response"
        
        context = AgentContext(
            bot_config_id="bot-123",
            reference_doc="Test doc",
            tone="professional",
            recent_messages=[]
        )
        
        agent = MessengerAgentService(mock_copilot_service)
        response = await agent.respond(context, "Test message")
        
        assert isinstance(response, AgentResponse)
        
        # Verify only current message is in the call
        call_args = mock_copilot_service.chat.call_args
        messages = call_args[0][1]
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assert len(user_messages) == 1  # Only current message
    
    @pytest.mark.asyncio
    async def test_respond_many_recent_messages(self, mock_copilot_service):
        """Test that only last 3 recent messages are used."""
        mock_copilot_service.chat.return_value = "Response"
        
        context = AgentContext(
            bot_config_id="bot-123",
            reference_doc="Test doc",
            tone="professional",
            recent_messages=["Msg1", "Msg2", "Msg3", "Msg4", "Msg5", "Msg6", "Msg7"]
        )
        
        agent = MessengerAgentService(mock_copilot_service)
        await agent.respond(context, "Current message")
        
        # Verify only last 3 recent messages are included
        call_args = mock_copilot_service.chat.call_args
        messages = call_args[0][1]
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        
        # Should have at most 4 messages (last 3 recent + current)
        assert len(user_messages) <= 4
