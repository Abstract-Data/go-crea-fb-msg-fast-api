"""FastAPI application initialization."""

import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.mcp import MCPIntegration

from src.api import health, webhook
from src.config import get_settings
from src.db.client import get_supabase_client
from src.logging_config import setup_logfire
from src.middleware.correlation_id import CorrelationIDMiddleware
from src.services.copilot_service import CopilotService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    # Startup
    settings = get_settings()
    
    # Initialize Logfire for observability
    setup_logfire()
    
    # Initialize Sentry if DSN is provided
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=True,
            integrations=[
                FastApiIntegration(),
                MCPIntegration(),
            ],
        )
    
    # Initialize Supabase client
    supabase = get_supabase_client()
    app.state.supabase = supabase
    
    # Check Copilot availability
    copilot = CopilotService(
        base_url=settings.copilot_cli_host,
        enabled=settings.copilot_enabled
    )
    app.state.copilot = copilot
    
    if settings.copilot_enabled:
        is_available = await copilot.is_available()
        if not is_available:
            print("Warning: Copilot SDK not available, will use OpenAI fallback")
    
    yield
    
    # Shutdown
    # Cleanup if needed


# Create FastAPI app
app = FastAPI(
    title="Facebook Messenger AI Bot",
    description="AI-powered Facebook Messenger bot using Copilot SDK and PydanticAI",
    version="0.1.0",
    lifespan=lifespan
)

# Correlation ID middleware (must be first for request tracing)
app.add_middleware(CorrelationIDMiddleware)

# CORS middleware (if needed for webhook testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
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
    return {"message": "Facebook Messenger AI Bot API"}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV") == "local"
    )
