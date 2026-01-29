# Cursor Implementation Prompt: PydanticAI Gateway Integration

## Context

You are refactoring a Facebook Messenger AI Bot project to use **PydanticAI Gateway (PAIG)** instead of the current GitHub Copilot SDK implementation. The goal is to simplify the LLM integration, add multi-tenant SaaS support, and enable per-tenant cost tracking.

## Current State

The project currently uses:
- `CopilotService` in `src/services/copilot_service.py` - wraps GitHub Copilot SDK with OpenAI fallback
- `MessengerAgentService` in `src/services/agent_service.py` - uses CopilotService for responses
- Supabase for database (bot_configurations, reference_documents, message_history)
- FastAPI with async architecture
- PydanticAI is already a dependency but not used properly with the gateway

## Target State

Replace the complex Copilot SDK wrapper with native PydanticAI Gateway integration:
- Single-line model configuration: `Agent('gateway/openai:gpt-4o')`
- Per-tenant cost tracking via PAIG projects
- Structured outputs using PydanticAI's native result_type
- Remove all Copilot SDK-specific code
- Add multi-tenant support to database schema

---

## Implementation Tasks

### Task 1: Update Dependencies

Update `pyproject.toml`:
```toml
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.0.0",
    "pydantic-ai>=1.16.0",  # UPDATE: Ensure gateway support
    "pydantic-settings>=2.0.0",
    "httpx>=0.25.0",
    "beautifulsoup4>=4.12.0",
    "supabase>=2.0.0",
    "typer>=0.9.0",
    "python-dotenv>=1.0.0",
    "sentry-sdk[fastapi,pydantic-ai]>=2.50.0",
    "pydantic-ai-slim[logfire]>=1.16.0",  # ADD: For observability
]
```

### Task 2: Update Configuration

Replace `src/config.py` with updated settings:

```python
"""Application configuration using Pydantic BaseSettings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Facebook Configuration
    facebook_page_access_token: str = Field(
        ...,
        description="Facebook Page access token"
    )
    facebook_verify_token: str = Field(
        ...,
        description="Webhook verification token"
    )
    facebook_app_secret: str | None = Field(
        default=None,
        description="Facebook App secret (optional, for signature verification)"
    )
    
    # Supabase Configuration
    supabase_url: str = Field(
        ...,
        description="Supabase project URL"
    )
    supabase_service_key: str = Field(
        ...,
        description="Supabase service role key"
    )
    
    # PydanticAI Gateway Configuration (NEW)
    pydantic_ai_gateway_api_key: str = Field(
        ...,
        description="PydanticAI Gateway API key (paig_xxx)"
    )
    default_model: str = Field(
        default="gateway/openai:gpt-4o",
        description="Default LLM model to use via PAIG"
    )
    fallback_model: str = Field(
        default="gateway/anthropic:claude-3-5-sonnet-latest",
        description="Fallback model if primary fails"
    )
    
    # REMOVED: Copilot SDK Configuration
    # copilot_cli_host: str  # DELETED
    # copilot_enabled: bool  # DELETED
    
    # OpenAI Configuration (kept for direct fallback if needed)
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (legacy fallback)"
    )
    
    # Environment
    env: Literal["local", "railway", "prod"] = Field(
        default="local",
        description="Current environment"
    )
    
    # Sentry Configuration
    sentry_dsn: str | None = Field(
        default=None,
        description="Sentry DSN for error tracking (optional)"
    )
    sentry_traces_sample_rate: float = Field(
        default=1.0,
        description="Sentry traces sample rate (0.0 to 1.0)"
    )
    
    # Logfire Configuration (NEW - pairs with PAIG)
    logfire_token: str | None = Field(
        default=None,
        description="Pydantic Logfire token for AI observability"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### Task 3: Create New Agent Service

**DELETE** `src/services/copilot_service.py` entirely.

**REPLACE** `src/services/agent_service.py` with:

```python
"""PydanticAI agent service using Gateway."""

import logging
from typing import Any

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
```

### Task 4: Update Agent Models

Update `src/models/agent_models.py` to work better with PydanticAI:

```python
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
```

### Task 5: Update Main Application

Update `src/main.py` to remove Copilot initialization and add Logfire:

```python
"""FastAPI application initialization."""

import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration

from src.api import health, webhook
from src.config import get_settings
from src.db.client import get_supabase_client

# Optional: Logfire for AI observability
try:
    import logfire
    LOGFIRE_AVAILABLE = True
except ImportError:
    LOGFIRE_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    settings = get_settings()
    
    # Initialize Sentry if DSN is provided
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=True,
            integrations=[
                FastApiIntegration(),
            ],
        )
    
    # Initialize Logfire for AI observability (pairs with PAIG)
    if LOGFIRE_AVAILABLE and settings.logfire_token:
        logfire.configure(token=settings.logfire_token)
        logfire.instrument_pydantic_ai()  # Auto-instrument all PydanticAI calls
        print("Logfire AI observability enabled")
    
    # Initialize Supabase client
    supabase = get_supabase_client()
    app.state.supabase = supabase
    
    # REMOVED: Copilot service initialization
    # PydanticAI Gateway doesn't require app-level initialization
    # Each agent service instance handles its own connection
    
    print(f"Using model: {settings.default_model}")
    print(f"Environment: {settings.env}")
    
    yield
    
    # Shutdown - cleanup if needed


# Create FastAPI app
app = FastAPI(
    title="Facebook Messenger AI Bot",
    description="AI-powered Facebook Messenger bot using PydanticAI Gateway",
    version="0.2.0",  # Version bump for PAIG migration
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])


@app.get("/")
def root():
    """Root endpoint."""
    settings = get_settings()
    return {
        "message": "Facebook Messenger AI Bot API",
        "model": settings.default_model,
        "version": "0.2.0"
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV") == "local"
    )
```

### Task 6: Update Webhook Handler

Update `src/api/webhook.py` to use the new agent service:

```python
"""Facebook webhook endpoints."""

import logging
from fastapi import APIRouter, Request, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse

from src.config import get_settings
from src.db.repository import (
    get_bot_configuration_by_page_id,
    get_reference_document,
    save_message_history,
)
from src.models.agent_models import AgentContext
from src.services.agent_service import MessengerAgentService
from src.services.facebook_service import send_facebook_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def verify_webhook(request: Request):
    """Facebook webhook verification endpoint."""
    settings = get_settings()
    
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == settings.facebook_verify_token:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(challenge)
    
    logger.warning("Webhook verification failed")
    return Response(status_code=403)


@router.post("")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming Facebook Messenger webhook events."""
    payload = await request.json()
    
    if payload.get("object") != "page":
        return {"status": "ignored"}
    
    for entry in payload.get("entry", []):
        page_id = entry.get("id")
        
        for messaging_event in entry.get("messaging", []):
            sender_id = messaging_event.get("sender", {}).get("id")
            message = messaging_event.get("message", {})
            message_text = message.get("text")
            
            if not message_text:
                continue
            
            # Process message in background
            background_tasks.add_task(
                process_message,
                page_id=page_id,
                sender_id=sender_id,
                message_text=message_text,
            )
    
    return {"status": "ok"}


async def process_message(page_id: str, sender_id: str, message_text: str):
    """Process incoming message and send response."""
    try:
        # Get bot configuration
        bot_config = get_bot_configuration_by_page_id(page_id)
        if not bot_config:
            logger.error(f"No bot configuration found for page_id: {page_id}")
            return
        
        # Get reference document
        ref_doc = get_reference_document(bot_config.reference_doc_id)
        if not ref_doc:
            logger.error(f"No reference document found: {bot_config.reference_doc_id}")
            return
        
        # Build agent context
        context = AgentContext(
            bot_config_id=bot_config.id,
            reference_doc=ref_doc["content"],
            tone=bot_config.tone,
            recent_messages=[],  # TODO: Load from message_history
            tenant_id=getattr(bot_config, 'tenant_id', None),
        )
        
        # Get response from agent (NEW: Using PydanticAI Gateway)
        agent_service = MessengerAgentService()
        response = await agent_service.respond(context, message_text)
        
        # Send response via Facebook
        await send_facebook_message(
            recipient_id=sender_id,
            message_text=response.message,
            page_access_token=bot_config.facebook_page_access_token,
        )
        
        # Save to history
        save_message_history(
            bot_id=bot_config.id,
            sender_id=sender_id,
            message_text=message_text,
            response_text=response.message,
            confidence=response.confidence,
            requires_escalation=response.requires_escalation,
        )
        
        logger.info(
            f"Processed message for page {page_id}: "
            f"confidence={response.confidence}, escalation={response.requires_escalation}"
        )
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
```

### Task 7: Update Reference Doc Service

Update `src/services/reference_doc.py` to use PydanticAI Gateway:

```python
"""Reference document builder using PydanticAI Gateway."""

import hashlib
import logging
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.config import get_settings
from src.db.repository import create_reference_document

logger = logging.getLogger(__name__)


class ReferenceDocument(BaseModel):
    """Structured reference document output."""
    overview: str = Field(..., description="Brief overview of the website/organization")
    key_topics: list[str] = Field(..., description="Main topics covered")
    common_questions: list[str] = Field(..., description="Anticipated FAQs")
    important_details: str = Field(..., description="Critical information to remember")
    contact_info: str | None = Field(None, description="Contact information if available")


async def build_reference_document(
    website_url: str,
    text_chunks: list[str],
) -> str:
    """
    Build a reference document from scraped website content.
    
    Args:
        website_url: Source website URL
        text_chunks: List of text chunks from scraping
        
    Returns:
        Synthesized markdown reference document
    """
    settings = get_settings()
    
    # Create synthesis agent
    agent = Agent(
        settings.default_model,
        result_type=ReferenceDocument,
        system_prompt="""You are a content synthesis assistant. 
Your job is to create comprehensive reference documents for AI agents that will answer questions about websites.
Focus on extracting: policies, services, FAQs, contact information, and key positions/statements.
Be thorough but concise.""",
    )
    
    # Build prompt with all chunks
    chunks_text = "\n\n---\n\n".join(
        f"CHUNK {i+1}:\n{chunk}" 
        for i, chunk in enumerate(text_chunks)
    )
    
    prompt = f"""Analyze the following content from {website_url} and create a structured reference document.

WEBSITE CONTENT:
{chunks_text}

Create a comprehensive reference document that an AI agent can use to answer questions about this website."""
    
    # Run synthesis
    result = await agent.run(prompt)
    doc = result.data
    
    # Convert to markdown
    markdown = f"""# Reference Document: {website_url}

## Overview
{doc.overview}

## Key Topics
{chr(10).join(f"- {topic}" for topic in doc.key_topics)}

## Common Questions
{chr(10).join(f"- {q}" for q in doc.common_questions)}

## Important Details
{doc.important_details}

## Contact Information
{doc.contact_info or "Not available"}
"""
    
    return markdown


async def create_and_store_reference_document(
    website_url: str,
    text_chunks: list[str],
) -> str:
    """
    Create reference document and store in database.
    
    Returns:
        Reference document ID
    """
    # Build document
    content = await build_reference_document(website_url, text_chunks)
    
    # Calculate hash
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    
    # Store in database
    doc_id = create_reference_document(
        content=content,
        source_url=website_url,
        content_hash=content_hash,
    )
    
    logger.info(f"Created reference document: {doc_id}")
    return doc_id
```

### Task 8: Add Database Migration for Multi-Tenant

Create `migrations/002_multi_tenant.sql`:

```sql
-- Multi-tenant support migration
-- Adds tenant tracking for SaaS model

-- Create tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    email text,
    paig_project_id text,  -- Link to PydanticAI Gateway project
    monthly_budget_cents integer DEFAULT 10000,  -- $100 default
    plan text DEFAULT 'free',  -- free, pro, enterprise
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Add tenant_id to existing tables
ALTER TABLE bot_configurations 
ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);

ALTER TABLE reference_documents 
ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);

ALTER TABLE message_history 
ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES tenants(id);

-- Create usage tracking table
CREATE TABLE IF NOT EXISTS usage_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
    bot_id uuid REFERENCES bot_configurations(id) ON DELETE CASCADE,
    model text NOT NULL,
    tokens_in integer DEFAULT 0,
    tokens_out integer DEFAULT 0,
    cost_cents numeric(10,4) DEFAULT 0,
    created_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tenants_email ON tenants(email);
CREATE INDEX IF NOT EXISTS idx_bot_configurations_tenant_id ON bot_configurations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_tenant_id ON usage_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs(created_at);

-- Trigger for tenants updated_at
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### Task 9: Update Environment Variables

Update `.env.example`:

```bash
# Facebook Messenger Configuration
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token_here
FACEBOOK_VERIFY_TOKEN=your_verify_token_here
FACEBOOK_APP_SECRET=your_app_secret_here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here

# PydanticAI Gateway Configuration (NEW)
PYDANTIC_AI_GATEWAY_API_KEY=paig_your_key_here
DEFAULT_MODEL=gateway/openai:gpt-4o
FALLBACK_MODEL=gateway/anthropic:claude-3-5-sonnet-latest

# REMOVED: Copilot SDK Configuration
# COPILOT_CLI_HOST=http://localhost:5909  # DELETED
# COPILOT_ENABLED=True  # DELETED

# OpenAI API Key (legacy fallback - optional)
OPENAI_API_KEY=your_openai_api_key_here

# Environment
ENV=local

# Sentry Configuration
SENTRY_DSN=your_sentry_dsn_here
SENTRY_TRACES_SAMPLE_RATE=1.0

# Pydantic Logfire (NEW - for AI observability)
LOGFIRE_TOKEN=your_logfire_token_here
```

### Task 10: Update Tests

Create/update `tests/unit/test_agent_service.py`:

```python
"""Tests for PydanticAI Gateway agent service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models.agent_models import AgentContext, AgentResponse
from src.services.agent_service import MessengerAgentService, MessengerAgentDeps


class TestMessengerAgentService:
    """Test suite for MessengerAgentService."""
    
    @pytest.fixture
    def agent_context(self):
        """Sample agent context."""
        return AgentContext(
            bot_config_id="test-bot-id",
            reference_doc="# Test Reference\n\nThis is a test document about our services.",
            tone="professional",
            recent_messages=["Hello", "How can I help?"],
        )
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        with patch('src.services.agent_service.get_settings') as mock:
            settings = MagicMock()
            settings.pydantic_ai_gateway_api_key = "paig_test_key"
            settings.default_model = "gateway/openai:gpt-4o"
            settings.fallback_model = "gateway/anthropic:claude-3-5-sonnet-latest"
            mock.return_value = settings
            yield mock
    
    @pytest.mark.asyncio
    async def test_respond_returns_agent_response(self, agent_context, mock_settings):
        """Test that respond returns a properly typed AgentResponse."""
        with patch('src.services.agent_service.Agent') as MockAgent:
            # Setup mock
            mock_result = MagicMock()
            mock_result.data = AgentResponse(
                message="Test response",
                confidence=0.9,
                requires_escalation=False,
            )
            
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run.return_value = mock_result
            MockAgent.return_value = mock_agent_instance
            
            # Test
            service = MessengerAgentService()
            response = await service.respond(agent_context, "What services do you offer?")
            
            # Assertions
            assert isinstance(response, AgentResponse)
            assert response.message == "Test response"
            assert response.confidence == 0.9
            assert not response.requires_escalation
    
    @pytest.mark.asyncio
    async def test_respond_handles_errors_gracefully(self, agent_context, mock_settings):
        """Test that errors result in escalation response."""
        with patch('src.services.agent_service.Agent') as MockAgent:
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run.side_effect = Exception("API Error")
            MockAgent.return_value = mock_agent_instance
            
            service = MessengerAgentService()
            response = await service.respond(agent_context, "Test message")
            
            assert response.requires_escalation is True
            assert response.confidence == 0.0
            assert "error" in response.escalation_reason.lower()
    
    def test_agent_response_should_escalate(self):
        """Test escalation threshold logic."""
        # High confidence, no escalation flag
        response1 = AgentResponse(message="Test", confidence=0.9, requires_escalation=False)
        assert response1.should_escalate(threshold=0.7) is False
        
        # Low confidence
        response2 = AgentResponse(message="Test", confidence=0.5, requires_escalation=False)
        assert response2.should_escalate(threshold=0.7) is True
        
        # Escalation flag set
        response3 = AgentResponse(message="Test", confidence=0.9, requires_escalation=True)
        assert response3.should_escalate(threshold=0.7) is True
```

---

## Files to DELETE

After implementing the above, delete these files:
- `src/services/copilot_service.py` (replaced by PydanticAI Gateway)

## Files to MODIFY

1. `pyproject.toml` - Update dependencies
2. `src/config.py` - New settings
3. `src/services/agent_service.py` - Complete rewrite
4. `src/services/reference_doc.py` - Use PAIG for synthesis
5. `src/models/agent_models.py` - Add fields
6. `src/main.py` - Remove Copilot, add Logfire
7. `src/api/webhook.py` - Use new agent service
8. `.env.example` - New environment variables

## Files to CREATE

1. `migrations/002_multi_tenant.sql` - Multi-tenant schema
2. `tests/unit/test_agent_service.py` - New tests

---

## Verification Steps

After implementation, verify:

1. **Run tests**: `uv run pytest -v`
2. **Check types**: `uv run mypy src/`
3. **Lint**: `uv run ruff check .`
4. **Start server**: `uv run uvicorn src.main:app --reload`
5. **Test endpoint**: `curl http://localhost:8000/health`

## Environment Setup for Testing

```bash
# Set required environment variables
export PYDANTIC_AI_GATEWAY_API_KEY="paig_your_test_key"
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_KEY="your_key"
export FACEBOOK_PAGE_ACCESS_TOKEN="test_token"
export FACEBOOK_VERIFY_TOKEN="test_verify"
```

---

## Notes for Implementation

1. **PydanticAI Gateway is currently free** during beta - no API cost concerns for testing
2. **Structured outputs** via `result_type=AgentResponse` ensure type-safe responses
3. **FallbackModel** provides automatic failover between providers
4. **Logfire integration** is optional but recommended for observability
5. The **AGPL-3.0 license** of PAIG means you must open-source modifications to the gateway itself (not your application code)
