"""Agent context and response models."""

from pydantic import BaseModel


class AgentContext(BaseModel):
    """Context for agent responses."""
    bot_config_id: str
    reference_doc: str
    tone: str
    recent_messages: list[str]  # Keep simple for now


class AgentResponse(BaseModel):
    """Agent response with confidence and escalation flags."""
    message: str
    confidence: float
    requires_escalation: bool = False
    escalation_reason: str | None = None
