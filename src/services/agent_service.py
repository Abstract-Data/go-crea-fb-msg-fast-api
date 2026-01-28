"""PydanticAI agent service using Gateway."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.fallback import FallbackModel

from src.config import get_settings
from src.models.agent_models import AgentContext, AgentResponse

logger = logging.getLogger(__name__)

# Project root (parent of src/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENT_SYSTEM_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "agent_system_instructions.md"


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
        
        # Create agent with structured output (system_prompt is registered below via decorator)
        self.agent = Agent(
            model_name,
            output_type=AgentResponse,
            system_prompt=(),
            retries=2,
            deps_type=MessengerAgentDeps,
        )
        self.agent.system_prompt(dynamic=True)(self._build_system_prompt)

        # Register tools
        self._register_tools()
        
        logger.info(f"MessengerAgentService initialized with model: {model_name}")
    
    def _load_system_prompt_template(self) -> str:
        """Load system prompt from prompts/agent_system_instructions.md."""
        if not _AGENT_SYSTEM_PROMPT_PATH.exists():
            raise FileNotFoundError(
                f"Agent system prompt not found: {_AGENT_SYSTEM_PROMPT_PATH}"
            )
        return _AGENT_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    def _build_system_prompt(self, ctx: RunContext[MessengerAgentDeps]) -> str:
        """Build dynamic system prompt from context and prompts/agent_system_instructions.md."""
        deps = ctx.deps
        template = self._load_system_prompt_template()
        # Use only the body after --- (title/description above are for humans)
        if "---" in template:
            template = template.split("---", 1)[-1].strip()
        recent = (
            "\n".join(deps.recent_messages[-6:])
            if deps.recent_messages
            else "No previous messages"
        )
        return template.replace("{{ tone }}", deps.tone).replace(
            "{{ reference_doc }}", deps.reference_doc
        ).replace("{{ recent_messages }}", recent)
    
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
            
            # Result.output is already typed as AgentResponse
            response = result.output
            
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
            output_type=AgentResponse,
            system_prompt=self._build_system_prompt,
        )
        
        deps = MessengerAgentDeps(
            reference_doc=context.reference_doc,
            tone=context.tone,
            recent_messages=context.recent_messages,
        )
        
        result = await fallback_agent.run(user_message, deps=deps)
        return result.output


# Factory function for dependency injection
def get_agent_service(model: str | None = None) -> MessengerAgentService:
    """Get agent service instance."""
    return MessengerAgentService(model=model)
