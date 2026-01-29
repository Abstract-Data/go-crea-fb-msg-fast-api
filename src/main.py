"""FastAPI application initialization."""

import asyncio
import os
import signal
from contextlib import asynccontextmanager

import logfire
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


# =============================================================================
# Graceful Shutdown Infrastructure
# =============================================================================

# Shutdown event for graceful termination
shutdown_event = asyncio.Event()

# Track pending background tasks for graceful shutdown
_pending_tasks: set[asyncio.Task] = set()

# Graceful shutdown timeout (seconds) - wait this long for tasks to complete
GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 30.0


def track_background_task(task: asyncio.Task) -> None:
    """
    Track a background task for graceful shutdown.

    Call this when adding tasks via BackgroundTasks or asyncio.create_task()
    if you want them to complete before shutdown.

    Example:
        task = asyncio.create_task(process_message(...))
        track_background_task(task)
    """
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


def is_shutting_down() -> bool:
    """Check if the application is in shutdown mode."""
    return shutdown_event.is_set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful shutdown support."""
    # Startup
    settings = get_settings()

    # Initialize Logfire for observability
    setup_logfire(app)

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

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler(sig_name: str):
        """Handle shutdown signals gracefully."""
        logfire.info(
            "Received shutdown signal, initiating graceful shutdown",
            signal=sig_name,
            pending_tasks=len(_pending_tasks),
        )
        shutdown_event.set()

    # Register signal handlers (only works on Unix-like systems)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: signal_handler(s.name),
            )
        logfire.info("Signal handlers registered for graceful shutdown")
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        logfire.warning(
            "Signal handlers not supported on this platform, "
            "graceful shutdown may not work as expected"
        )

    # REMOVED: Copilot service initialization
    # PydanticAI Gateway doesn't require app-level initialization
    # Each agent service instance handles its own connection

    logfire.info(
        "Application startup complete",
        model=settings.default_model,
        environment=settings.env,
    )
    print(f"Using model: {settings.default_model}")
    print(f"Environment: {settings.env}")

    yield

    # ==========================================================================
    # Graceful Shutdown
    # ==========================================================================
    logfire.info(
        "Application shutdown initiated",
        pending_tasks=len(_pending_tasks),
    )

    if _pending_tasks:
        logfire.info(
            "Waiting for pending background tasks to complete",
            task_count=len(_pending_tasks),
            timeout_seconds=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
        )

        # Wait for pending tasks with timeout
        done, pending = await asyncio.wait(
            _pending_tasks,
            timeout=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
            return_when=asyncio.ALL_COMPLETED,
        )

        if pending:
            logfire.warning(
                "Cancelling remaining tasks after timeout",
                completed_count=len(done),
                cancelled_count=len(pending),
            )
            for task in pending:
                task.cancel()

            # Wait briefly for cancellation to complete
            await asyncio.gather(*pending, return_exceptions=True)
        else:
            logfire.info(
                "All background tasks completed successfully",
                completed_count=len(done),
            )
    else:
        logfire.info("No pending background tasks during shutdown")

    logfire.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Facebook Messenger AI Bot",
    description="AI-powered Facebook Messenger bot using PydanticAI Gateway",
    version="0.2.0",  # Version bump for PAIG migration
    lifespan=lifespan,
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
    settings = get_settings()
    return {
        "message": "Facebook Messenger AI Bot API",
        "model": settings.default_model,
        "version": "0.2.0",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "src.main:app", host="0.0.0.0", port=port, reload=os.getenv("ENV") == "local"
    )
