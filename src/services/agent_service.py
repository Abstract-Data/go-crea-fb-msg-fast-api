"""PydanticAI agent service using Gateway."""

import logging
import re
from pathlib import Path

import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.fallback import FallbackModel

from src.config import get_settings
from src.db.repository import search_page_chunks
from src.models.agent_models import AgentContext, AgentResponse
from src.services.embedding_service import embed_query

logger = logging.getLogger(__name__)

# Project root (parent of src/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENT_SYSTEM_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "agent_system_instructions.md"


class MessengerAgentDeps(BaseModel):
    """Dependencies passed to the agent at runtime."""

    reference_doc_id: str
    reference_doc: str
    tone: str
    recent_messages: list[str] = Field(default_factory=list)
    tenant_id: str | None = None
    user_name: str | None = None
    user_location: str | None = None


class MessengerAgentService:
    """Service for generating AI agent responses using PydanticAI Gateway."""

    def __init__(self, model: str | None = None):
        """
        Initialize agent service with PydanticAI Gateway.

        Args:
            model: Model string (e.g., 'gateway/anthropic:claude-3-5-sonnet-latest')
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
        if "---" in template:
            template = template.split("---", 1)[-1].strip()
        recent = (
            "\n".join(deps.recent_messages[-6:])
            if deps.recent_messages
            else "No previous messages"
        )
        prompt = (
            template.replace("{{ tone }}", deps.tone)
            .replace("{{ reference_doc }}", deps.reference_doc)
            .replace("{{ recent_messages }}", recent)
        )
        if deps.user_name:
            prompt = re.sub(
                r"{% if user_name %}\s*(.*?)\s*{% endif %}",
                lambda m: m.group(1).replace("{{ user_name }}", deps.user_name),
                prompt,
                count=1,
                flags=re.DOTALL,
            )
        else:
            prompt = re.sub(
                r"{% if user_name %}.*?{% endif %}",
                "",
                prompt,
                count=1,
                flags=re.DOTALL,
            )
        if deps.user_location:
            prompt = re.sub(
                r"{% if user_location %}\s*(.*?)\s*{% endif %}",
                lambda m: m.group(1).replace("{{ user_location }}", deps.user_location),
                prompt,
                count=1,
                flags=re.DOTALL,
            )
        else:
            prompt = re.sub(
                r"{% if user_location %}.*?{% endif %}",
                "",
                prompt,
                count=1,
                flags=re.DOTALL,
            )
        return prompt

    def _register_tools(self) -> None:
        """Register any tools the agent can use."""

        @self.agent.tool
        async def check_reference_coverage(
            ctx: RunContext[MessengerAgentDeps], topic: str
        ) -> str:
            """Check if a topic is covered in the reference document."""
            ref_doc = ctx.deps.reference_doc.lower()
            if topic.lower() in ref_doc:
                return f"Topic '{topic}' is covered in the reference document."
            return f"Topic '{topic}' is NOT covered. Consider escalating to human."

        @self.agent.tool
        async def search_pages(
            ctx: RunContext[MessengerAgentDeps], query: str
        ) -> str:
            """Search scraped website pages for specific information.

            Use this when you need to find detailed information that may not be
            in the overview, such as specific policies, contact details, or
            facts about particular topics.
            """
            logfire.info(
                "Agent searching scraped pages beyond reference doc",
                tool="search_pages",
                query=query[:200],
                reference_doc_id=ctx.deps.reference_doc_id,
            )
            settings = get_settings()
            limit = settings.search_result_limit
            query_embedding = await embed_query(query)
            if not query_embedding:
                logfire.warning(
                    "search_pages skipped: empty query or embedding failed",
                    query_length=len(query),
                )
                return "Search could not be run (empty query or embedding failed)."
            results = search_page_chunks(
                query_embedding=query_embedding,
                reference_doc_id=ctx.deps.reference_doc_id,
                limit=limit,
            )
            if not results:
                logfire.info(
                    "search_pages returned no matches",
                    query=query[:200],
                    reference_doc_id=ctx.deps.reference_doc_id,
                )
                return "No matching content found in the scraped pages."
            logfire.info(
                "search_pages returned results from scraped pages",
                result_count=len(results),
                query=query[:200],
                reference_doc_id=ctx.deps.reference_doc_id,
            )
            parts = []
            for r in results:
                page_url = r.get("page_url", "")
                content = r.get("content", "")[:500]
                parts.append(f"[Source: {page_url}]\n{content}...")
            return "\n\n---\n\n".join(parts)

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
            reference_doc_id=context.reference_doc_id,
            reference_doc=context.reference_doc,
            tone=context.tone,
            recent_messages=context.recent_messages,
            tenant_id=getattr(context, "tenant_id", None),
            user_name=getattr(context, "user_name", None),
            user_location=getattr(context, "user_location", None),
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
                escalation_reason=f"Agent error: {str(e)}",
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
            reference_doc_id=context.reference_doc_id,
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
