"""Agent context and response models."""

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Context for agent responses."""
    bot_config_id: str
    reference_doc: str
    tone: str
    recent_messages: list[str] = Field(default_factory=list)
    tenant_id: str | None = None  # NEW: For multi-tenant support


class AgentResponse(BaseModel):
    """
    Agent response with confidence and escalation flags.
    
    This model is used as result_type for PydanticAI,
    ensuring structured, typed responses from the LLM.
    """
    message: str = Field(
        ...,
        max_length=500,
        description="Response message to send to user (max 500 chars for Messenger)"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0"
    )
    requires_escalation: bool = Field(
        default=False,
        description="Whether this should be escalated to a human"
    )
    escalation_reason: str | None = Field(
        default=None,
        description="Reason for escalation if requires_escalation is True"
    )
    
    def should_escalate(self, threshold: float = 0.7) -> bool:
        """Check if response should be escalated based on confidence threshold."""
        return self.requires_escalation or self.confidence < threshold
