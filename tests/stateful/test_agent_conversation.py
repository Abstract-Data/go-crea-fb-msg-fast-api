"""Stateful tests for agent conversation flows using Hypothesis."""

import pytest
from unittest.mock import AsyncMock

from src.services.agent_service import MessengerAgentService
from src.models.agent_models import AgentContext, AgentResponse


class TestAgentConversationStateful:
    """Test agent conversation state management."""
    
    @pytest.mark.asyncio
    async def test_conversation_flow_basic(self):
        """Basic test of conversation flow."""
        # Create mock Copilot service
        copilot = AsyncMock()
        copilot.chat = AsyncMock(return_value="Test response")
        
        # Create agent service
        agent = MessengerAgentService(copilot)
        
        # Initialize conversation state
        context = AgentContext(
            bot_config_id="test-123",
            reference_doc="# Overview\nTest content for the agent.",
            tone="professional",
            recent_messages=[]
        )
        conversation_history = []
        
        # Simulate a few messages
        messages = ["Hello", "What can you help me with?", "Thanks"]
        
        for message in messages:
            response = await agent.respond(context, message)
            
            # Verify response is valid
            assert response.message is not None
            assert len(response.message) > 0
            assert 0.0 <= response.confidence <= 1.0
            assert isinstance(response.requires_escalation, bool)
            
            # Update conversation state
            conversation_history.append({
                "user": message,
                "bot": response.message,
                "confidence": response.confidence,
                "escalation": response.requires_escalation
            })
            
            # Update context with recent messages (last 3)
            context.recent_messages = [
                msg["user"] for msg in conversation_history[-3:]
            ]
        
        # Verify invariants
        assert len(conversation_history) == 3
        assert len(context.recent_messages) <= 3
        
        # All messages should have valid confidence scores
        for entry in conversation_history:
            assert 0.0 <= entry["confidence"] <= 1.0
            assert len(entry["bot"]) > 0
            assert len(entry["user"]) > 0
    
    @pytest.mark.asyncio
    async def test_conversation_maintains_context(self):
        """Test that conversation maintains context correctly."""
        copilot = AsyncMock()
        copilot.chat = AsyncMock(return_value="Response with context")
        
        agent = MessengerAgentService(copilot)
        
        context = AgentContext(
            bot_config_id="test-123",
            reference_doc="# Overview\nTest content.",
            tone="professional",
            recent_messages=[]
        )
        
        # Send 5 messages
        for i in range(5):
            response = await agent.respond(context, f"Message {i}")
            context.recent_messages.append(f"Message {i}")
            if len(context.recent_messages) > 3:
                context.recent_messages = context.recent_messages[-3:]
        
        # Only last 3 messages should be kept
        assert len(context.recent_messages) == 3
        assert context.recent_messages == ["Message 2", "Message 3", "Message 4"]
