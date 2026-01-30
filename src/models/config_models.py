"""Bot and Facebook configuration models."""

from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class WebsiteInput(BaseModel):
    """Website URL input for scraping."""

    url: str


class TonePreference(BaseModel):
    """Communication tone preference."""

    tone: str  # e.g. "professional", "friendly", "casual", "formal", "humorous"
    description: str | None = None


class FacebookConfig(BaseModel):
    """Facebook app configuration."""

    page_id: str
    page_access_token: str
    verify_token: str


class BotConfiguration(BaseModel):
    """Complete bot configuration."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page_id: str
    website_url: str
    reference_doc_id: str
    tone: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


class BotConfigurationCreate(BaseModel):
    """Parameters for creating a bot configuration.

    Replaces the long parameter list in create_bot_configuration() with a
    single type-safe parameter object.
    """

    page_id: str = Field(..., description="Facebook Page ID")
    website_url: str = Field(..., description="Source website URL")
    reference_doc_id: str = Field(..., description="Reference document UUID")
    tone: str = Field(
        ..., description="Communication tone (e.g., friendly, professional)"
    )
    facebook_page_access_token: str = Field(
        ..., description="Facebook Page access token"
    )
    facebook_verify_token: str = Field(..., description="Webhook verify token")
