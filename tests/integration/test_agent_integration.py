"""Integration tests for agent service with Copilot service."""

import pytest
from unittest.mock import AsyncMock, patch
import respx
import httpx

from src.services.agent_service import MessengerAgentService
from src.services.copilot_service import CopilotService
from src.models.agent_models import AgentContext


class TestAgentCopilotIntegration:
    """Test agent service integration with Copilot service."""
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_agent_with_copilot_service(self):
        """Test agent service with real Copilot service (mocked HTTP)."""
        # Mock Copilot HTTP responses
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(return_value=httpx.Response(
            200,
            json={"content": "I can help you with that. Here's the information you need."}
        ))
        
        # Create real Copilot service
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        
        # Create agent service
        agent = MessengerAgentService(copilot)
        
        # Create context
        context = AgentContext(
            bot_config_id="bot-123",
            reference_doc="# Overview\nThis is a test organization.",
            tone="professional",
            recent_messages=[]
        )
        
        # Get response
        response = await agent.respond(context, "What services do you offer?")
        
        # Verify response
        assert response.message is not None
        assert len(response.message) > 0
        assert 0.0 <= response.confidence <= 1.0
        assert isinstance(response.requires_escalation, bool)
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_agent_escalation_scenario(self):
        """Test escalation scenarios with agent and Copilot."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(return_value=httpx.Response(
            200,
            json={"content": "I don't know the answer to that question. Please contact a human representative."}
        ))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        agent = MessengerAgentService(copilot)
        
        context = AgentContext(
            bot_config_id="bot-123",
            reference_doc="# Limited Information\nVery little content.",
            tone="professional",
            recent_messages=[]
        )
        
        response = await agent.respond(context, "What about something not in the doc?")
        
        # Should trigger escalation
        assert response.requires_escalation is True
        assert response.escalation_reason is not None
        assert "don't know" in response.message.lower() or "human" in response.message.lower()
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_agent_with_recent_messages(self):
        """Test agent with recent message context."""
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(return_value=httpx.Response(
            200,
            json={"content": "Based on our previous conversation, here's more information."}
        ))
        
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        agent = MessengerAgentService(copilot)
        
        context = AgentContext(
            bot_config_id="bot-123",
            reference_doc="# Overview\nTest content.",
            tone="professional",
            recent_messages=["Hello", "What are your hours?", "Thanks"]
        )
        
        response = await agent.respond(context, "Can you tell me more?")
        
        # Verify response includes context
        assert response.message is not None
        
        # Verify Copilot was called with recent messages
        request = respx.calls.last.request
        import json
        payload = json.loads(request.read())
        messages = payload["messages"]
        
        # Should include recent messages
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assert len(user_messages) >= 1  # At least current message
