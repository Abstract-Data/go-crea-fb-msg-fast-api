"""Message history models for parameter objects."""

from pydantic import BaseModel, Field


class MessageHistoryCreate(BaseModel):
    """Parameters for saving message history.

    Replaces the long parameter list in save_message_history() with a
    single type-safe parameter object.
    """

    bot_id: str = Field(..., description="Bot configuration ID")
    sender_id: str = Field(..., description="Facebook user ID (PSID)")
    message_text: str = Field(..., description="User's incoming message")
    response_text: str = Field(..., description="Bot's response message")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Response confidence score"
    )
    requires_escalation: bool = Field(
        default=False,
        description="Whether message requires human escalation",
    )
    user_profile_id: str | None = Field(
        default=None,
        description="Associated user profile ID (optional)",
    )


class TestMessageCreate(BaseModel):
    """Parameters for saving a test REPL message.

    Replaces the long parameter list in save_test_message() with a
    single type-safe parameter object.
    """

    test_session_id: str = Field(..., description="Test session UUID")
    user_message: str = Field(..., description="User's test message")
    response_text: str = Field(..., description="Bot's response")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Response confidence score"
    )
    requires_escalation: bool = Field(
        default=False,
        description="Whether message requires human escalation",
    )
    escalation_reason: str | None = Field(
        default=None,
        description="Reason for escalation (if applicable)",
    )
