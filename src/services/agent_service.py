"""PydanticAI agent service."""

import time

import logfire

from src.models.agent_models import AgentContext, AgentResponse
from src.services.copilot_service import CopilotService


class MessengerAgentService:
    """Service for generating AI agent responses."""
    
    def __init__(self, copilot: CopilotService):
        """
        Initialize agent service.
        
        Args:
            copilot: CopilotService instance
        """
        self.copilot = copilot
    
    async def respond(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """
        Generate agent response to user message.
        
        Args:
            context: Agent context with reference doc and tone
            user_message: User's message text
            
        Returns:
            AgentResponse with message and confidence
        """
        start_time = time.time()
        
        logfire.info(
            "Processing agent response",
            user_message_length=len(user_message),
            tone=context.tone,
            reference_doc_length=len(context.reference_doc),
            recent_messages_count=len(context.recent_messages),
        )
        
        # Build system prompt
        system_prompt = f"""You are a {context.tone} assistant for a political/business Facebook page.
Use ONLY the following reference document as your source of truth:

{context.reference_doc}

Answer in under 300 characters where possible.
If the user asks about something not covered, say you don't know and suggest a human follow-up.
"""
        
        # Build messages list
        messages = [
            {"role": "user", "content": user_message}
        ]
        
        # Add recent messages for context
        for msg in context.recent_messages[-3:]:  # Last 3 messages
            messages.insert(-1, {"role": "user", "content": msg})
        
        # Call Copilot service
        response_text = await self.copilot.chat(system_prompt, messages)
        
        # Parse response and determine confidence
        # TODO: Use PydanticAI for structured output if needed
        confidence = 0.8  # Placeholder - could be determined by Copilot response
        
        # Check if escalation is needed
        requires_escalation = False
        escalation_reason = None
        
        if "don't know" in response_text.lower() or "human" in response_text.lower():
            requires_escalation = True
            escalation_reason = "Question outside knowledge base"
        
        elapsed = time.time() - start_time
        
        logfire.info(
            "Agent response generated",
            response_length=len(response_text),
            confidence=confidence,
            requires_escalation=requires_escalation,
            escalation_reason=escalation_reason,
            response_time_ms=elapsed * 1000,
        )
        
        return AgentResponse(
            message=response_text,
            confidence=confidence,
            requires_escalation=requires_escalation,
            escalation_reason=escalation_reason
        )
