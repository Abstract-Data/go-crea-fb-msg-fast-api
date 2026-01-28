"""PydanticAI agent service using Gateway."""

import logging

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.fallback import FallbackModel

from src.config import get_settings
from src.models.agent_models import AgentContext, AgentResponse

logger = logging.getLogger(__name__)


class MessengerAgentDeps(BaseModel):
    """Dependencies passed to the agent at runtime."""
    reference_doc: str
    tone: str
    recent_messages: list[str] = Field(default_factory=list)
    tenant_id: str | None = None  # For multi-tenant tracking


class MessengerAgentService:
    """Service for generating AI agent responses using PydanticAI Gateway."""
    
    def __init__(self, model: str | None = None):
        """
        Initialize agent service with PydanticAI Gateway.
        
        Args:
            model: Model string (e.g., 'gateway/openai:gpt-4o')
                   Defaults to settings.default_model
        """
        settings = get_settings()
        model_name = model or settings.default_model
        
        # Create agent with structured output
        self.agent = Agent(
            model_name,
            result_type=AgentResponse,
            system_prompt=self._build_system_prompt,
            retries=2,
        )
        
        # Register tools
        self._register_tools()
        
        logger.info(f"MessengerAgentService initialized with model: {model_name}")
    
    def _build_system_prompt(self, ctx: RunContext[MessengerAgentDeps]) -> str:
        """Build dynamic system prompt from context."""
        deps = ctx.deps
        
        return f"""You are a {deps.tone} assistant for a political/business Facebook page.

IMPORTANT RULES:
1. Use ONLY the following reference document as your source of truth
2. Answer in under 300 characters where possible
3. If asked about something not covered in the reference document, set requires_escalation=True
4. Be helpful, accurate, and maintain the specified tone

REFERENCE DOCUMENT:
{deps.reference_doc}

RECENT CONVERSATION CONTEXT:
{chr(10).join(deps.recent_messages[-3:]) if deps.recent_messages else "No previous messages"}
"""
    
    def _register_tools(self) -> None:
        """Register any tools the agent can use."""
        
        @self.agent.tool
        async def check_reference_coverage(
            ctx: RunContext[MessengerAgentDeps],
            topic: str
        ) -> str:
            """Check if a topic is covered in the reference document."""
            ref_doc = ctx.deps.reference_doc.lower()
            if topic.lower() in ref_doc:
                return f"Topic '{topic}' is covered in the reference document."
            return f"Topic '{topic}' is NOT covered. Consider escalating to human."
    
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
            AgentResponse with message, confidence, and escalation flags
        """
        # Build dependencies
        deps = MessengerAgentDeps(
            reference_doc=context.reference_doc,
            tone=context.tone,
            recent_messages=context.recent_messages,
            tenant_id=getattr(context, 'tenant_id', None),
        )
        
        try:
            # Run the agent
            result = await self.agent.run(user_message, deps=deps)
            
            # Result.data is already typed as AgentResponse
            response = result.data
            
            # Log usage for debugging
            logger.info(
                f"Agent response generated - "
                f"confidence: {response.confidence}, "
                f"escalation: {response.requires_escalation}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            # Return safe fallback response
            return AgentResponse(
                message="I'm having trouble processing your request. A team member will follow up with you shortly.",
                confidence=0.0,
                requires_escalation=True,
                escalation_reason=f"Agent error: {str(e)}"
            )
    
    async def respond_with_fallback(
        self,
        context: AgentContext,
        user_message: str,
    ) -> AgentResponse:
        """
        Generate response with automatic model fallback.
        
        Uses FallbackModel to try primary model first,
        then fallback model if primary fails.
        """
        settings = get_settings()
        
        # Create fallback model
        fallback_agent = Agent(
            FallbackModel(
                settings.default_model,
                settings.fallback_model,
            ),
            result_type=AgentResponse,
            system_prompt=self._build_system_prompt,
        )
        
        deps = MessengerAgentDeps(
            reference_doc=context.reference_doc,
            tone=context.tone,
            recent_messages=context.recent_messages,
        )
        
        result = await fallback_agent.run(user_message, deps=deps)
        return result.data


# Factory function for dependency injection
def get_agent_service(model: str | None = None) -> MessengerAgentService:
    """Get agent service instance."""
    return MessengerAgentService(model=model)
