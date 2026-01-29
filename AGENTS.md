You are an expert Python software engineer working on this project.

---

## Project Overview

**Tech Stack:**
- Python 3.12+ with uv for package management
- FastAPI for API services
- PostgreSQL/Supabase for database
- PydanticAI for AI agent framework
- GitHub Copilot SDK for LLM operations
- Pydantic Logfire for observability (structured logging, tracing, monitoring)
- Sentry for error tracking
- Pytest + Hypothesis for testing
- Ruff for linting and formatting
- Pre-commit hooks for code quality

**Architecture:**
- Async-first design (asyncio, async/await throughout)
- Dependency injection via FastAPI's DI system
- Repository pattern for database operations
- PydanticAI agent for message handling
- Copilot SDK with OpenAI fallback
- Structured logging with Logfire (request tracing, performance monitoring)

**File Structure:**
```
src/
├── api/           # FastAPI routers and endpoints
├── models/        # Pydantic models for validation
├── services/      # Business logic (scraper, agent, copilot, facebook)
├── db/            # Database client and repositories
└── cli/           # CLI commands for setup
tests/
├── unit/          # Fast, isolated unit tests
├── integration/   # Database and service integration tests
└── e2e/           # End-to-end API tests
migrations/        # Database migrations
```

---

## Commands You Must Know

### Development
```bash
uv sync                          # Install/sync dependencies
uv run pytest                    # Run all tests
uv run pytest -v --cov=src       # Run with coverage report
uv run pytest -k "test_name"     # Run specific test
uv run ruff check .              # Lint code
uv run ruff format .             # Format code
uv run uvicorn src.main:app --reload  # Start dev server
```

### Testing Strategy
```bash
# Fast feedback loop - run frequently
uv run pytest tests/unit -x     # Stop on first failure

# Before commits - comprehensive
uv run pytest --cov=src --cov-report=term-missing

# Property-based testing with Hypothesis
uv run pytest tests/unit/test_validation.py -v --hypothesis-show-statistics
```

### Database
```bash
# Apply migrations to Supabase
# Use Supabase Dashboard SQL Editor or Supabase CLI
supabase db push                 # If using Supabase CLI
```

### CLI Setup
```bash
uv run python -m src.cli.setup_cli setup  # Interactive bot setup
```

---

## Code Style Standards

### Naming Conventions

| Type | Convention | Examples |
|------|------------|----------|
| Functions/variables | `snake_case` | `get_bot_config`, `scrape_website` |
| Classes | `PascalCase` | `CopilotService`, `MessengerAgentService` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `COPILOT_CLI_HOST` |
| Private methods | `_leading_underscore` | `_validate_input`, `_fallback_to_openai` |
| Type variables | `PascalCase` with `T` prefix | `TModel`, `TResponse` |

### Modern Python Patterns

✅ **GOOD** — Type hints, async/await, context managers

```python
from typing import List
from contextlib import asynccontextmanager

async def get_bot_configuration_by_page_id(page_id: str) -> BotConfiguration | None:
    """Fetch bot configuration by Facebook Page ID."""
    if not page_id:
        raise ValueError("page_id is required")
    
    supabase = get_supabase_client()
    result = supabase.table("bot_configurations").select("*").eq("page_id", page_id).execute()
    
    if not result.data:
        return None
    
    return BotConfiguration(**result.data[0])
```

❌ **BAD** — No types, sync code, poor error handling

```python
def get_bot(id):
    # Synchronous, no type hints, swallows errors
    try:
        bot = db.query(Bot).filter(Bot.id == id).first()
        return bot
    except:
        return None
```

### FastAPI Route Standards

✅ **GOOD** — Proper dependencies, response models, error handling

```python
from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse
from src.config import get_settings

router = APIRouter()

@router.get("")
async def verify_webhook(request: Request):
    """Facebook webhook verification endpoint."""
    settings = get_settings()
    
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == settings.facebook_verify_token:
        return PlainTextResponse(challenge)
    
    return Response(status_code=403)
```

❌ **BAD** — No dependency injection, dict response, poor status codes

```python
@app.get("/webhook")
async def webhook(data: dict):
    if data.get("token") == "secret":  # Hardcoded!
        return {"status": "ok"}  # Wrong! Use proper response
    return {"error": "invalid"}  # Wrong! Use HTTPException
```

---

## Testing Practices

### Write Tests That Cover Edge Cases

```python
import pytest
from hypothesis import given, strategies as st
from src.services.scraper import scrape_website

class TestWebsiteScraper:
    """Test website scraping comprehensively."""

    def test_valid_url_accepted(self):
        """Valid URLs should be accepted."""
        # Test with mock HTTP response
        pass

    @pytest.mark.parametrize("invalid_url", [
        "",
        "not-a-url",
        "ftp://example.com",
        None,
    ])
    def test_invalid_urls_rejected(self, invalid_url):
        """Invalid URLs should be rejected."""
        with pytest.raises(ValueError):
            scrape_website(invalid_url)

    @pytest.mark.asyncio
    async def test_scraping_handles_timeout(self):
        """Scraper should handle timeouts gracefully."""
        # Test timeout handling
        pass
```

### Use Fixtures for Shared Setup

```python
@pytest.fixture
def mock_supabase_client():
    """Provide mock Supabase client for tests."""
    # Mock implementation
    pass

@pytest.fixture
async def sample_bot_config(mock_supabase_client):
    """Create a sample bot configuration for tests."""
    # Create test bot config
    pass
```

---

## Git Workflow

### Commit Messages
Follow conventional commits:
```
feat: add Facebook webhook verification endpoint
fix: resolve async issue in scraper service
refactor: extract Copilot service to separate module
test: add integration tests for agent service
docs: update README with deployment instructions
```

### Before Every Commit
```bash
uv run ruff format .              # Format code
uv run ruff check . --fix         # Fix auto-fixable issues
uv run pytest                     # All tests must pass
```

### PR Requirements
- Title format: `[component] Brief description`
- All tests passing in CI
- Code coverage > 85%
- No `ruff` warnings
- Updated documentation if API changes

---

## Security & Best Practices

### Environment Variables
```python
# ✅ GOOD - Use pydantic-settings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    
    facebook_page_access_token: str
    supabase_service_key: str
    copilot_enabled: bool = True

settings = Settings()
```

### Secrets Management
- Store secrets in `.env` (gitignored)
- Use Railway environment variables for production
- Never log sensitive data (tokens, keys)
- Sanitize error messages in production

### Database Queries
✅ **GOOD** — Use Supabase client (parameterized queries)

```python
async def get_bot_by_page_id(page_id: str) -> BotConfiguration | None:
    supabase = get_supabase_client()
    result = supabase.table("bot_configurations").select("*").eq("page_id", page_id).execute()
    # Supabase client handles parameterization
    return BotConfiguration(**result.data[0]) if result.data else None
```

❌ **BAD** — SQL injection risk (never use raw SQL strings)

```python
async def get_bot_by_page_id(page_id: str):
    query = f"SELECT * FROM bot_configurations WHERE page_id = '{page_id}'"  # NEVER DO THIS
    return await db.execute(query)
```

---

## Boundaries & Guardrails

### ✅ ALWAYS DO
- Write type hints for all functions and classes
- Use async/await for I/O operations
- Add docstrings to public functions
- Write tests for new features
- Run `ruff format` before committing
- Use dependency injection via FastAPI's `Depends()`
- Validate all external input with Pydantic models
- Use context managers for resources (HTTP clients, DB sessions)
- Handle Copilot SDK failures gracefully with OpenAI fallback

### ⚠️ ASK FIRST
- Adding new dependencies (check with `uv add`)
- Changing database schema (needs migration review)
- Modifying API contracts (breaks Facebook webhook)
- Changing authentication/authorization logic
- Altering CI/CD configuration
- Modifying Copilot SDK integration

### 🚫 NEVER DO
- Commit secrets, API keys, or credentials
- Use `print()` instead of logging (use `logfire` for structured logs)
- Swallow exceptions with bare `except:`
- Modify code in `site-packages/` or `.venv/`
- Store passwords in plain text
- Use `eval()` or `exec()` with user input
- Import from `__init__.py` files you didn't create
- Hardcode Facebook tokens or Supabase keys
- Skip error handling for external API calls
- Log sensitive data without masking (use `mask_pii()` and `redact_tokens()`)

---

## Common Patterns in This Project

### Background Tasks
```python
from fastapi import BackgroundTasks

@router.post("/webhook")
async def handle_webhook(
    payload: MessengerWebhookPayload,
    background_tasks: BackgroundTasks,
):
    # Process message in background
    background_tasks.add_task(process_message, payload)
    return {"status": "ok"}
```

### Error Handling
```python
from fastapi import HTTPException, status

try:
    bot_config = await get_bot_configuration_by_page_id(page_id)
except ValueError as e:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(e)
    )
```

### Dependency Injection
```python
from typing import Annotated
from fastapi import Depends, Request

async def get_copilot_service(request: Request) -> CopilotService:
    """Get Copilot service from app state."""
    return request.app.state.copilot

CopilotDep = Annotated[CopilotService, Depends(get_copilot_service)]

@router.post("/message")
async def process_message(
    message: str,
    copilot: CopilotDep
):
    # Use copilot service
    pass
```

### Async Service Calls
```python
async def scrape_and_synthesize(url: str) -> str:
    """Scrape website and synthesize reference document."""
    # Scrape
    chunks = await scrape_website(url)
    
    # Synthesize via Copilot
    copilot = CopilotService(base_url=settings.copilot_cli_host)
    reference_doc = await copilot.synthesize_reference(url, chunks)
    
    return reference_doc
```

### Structured Logging with Logfire
```python
import logfire
from src.logging_config import mask_pii, redact_tokens

# ✅ GOOD - Structured logging with context
logfire.info(
    "Processing agent response",
    message_length=len(message),
    confidence=response.confidence,
    requires_escalation=response.requires_escalation,
    bot_config_id=context.bot_config_id,
)

# ✅ GOOD - Error logging with context
try:
    result = await some_operation()
except Exception as e:
    logfire.error(
        "Operation failed",
        error=str(e),
        operation="some_operation",
        **redact_tokens({"token": sensitive_token})  # Redact sensitive data
    )
    raise

# ✅ GOOD - Timing and performance logging
with logfire.span("database_query"):
    result = await db.query(...)
    logfire.info("Query completed", row_count=len(result))

# ❌ BAD - Using print() or basic logging
print(f"Processing message: {message}")  # Never use print()
logging.info(f"Error: {error}")  # Use logfire instead for structured logs
```

---

## Operational Documentation Maintenance

### Updating RUNBOOK.md

The `RUNBOOK.md` file is the central repository for operational procedures and troubleshooting guides. Keep it current by updating it when discovering new issues, implementing fixes, or establishing new procedures.

**When to Update RUNBOOK.md:**
- ✅ When discovering a new operational issue or error pattern
- ✅ When implementing a fix for a documented issue
- ✅ When adding new debugging procedures or commands
- ✅ When establishing new alert thresholds or monitoring criteria
- ✅ When test failures reveal operational problems (see `TESTING.md`)
- ✅ When service behavior changes (e.g., fallback logic, retry strategies)
- ✅ When external dependencies change (Copilot SDK, Facebook API, Supabase)

**How to Update RUNBOOK.md:**

1. **Identify the issue or procedure:**
   - Does it fit in "Common Issues & Fixes"? (operational problems)
   - Does it fit in "Debug Commands"? (new debugging techniques)
   - Does it fit in "Service-Specific Troubleshooting"? (service-level issues)
   - Does it affect "Alert Thresholds"? (monitoring changes)

2. **Add or update the section:**
   - Use existing format and style
   - Include clear headings and subsections
   - Add code blocks for commands with explanations
   - Reference actual file paths and service names

3. **Include necessary details:**
   - **Symptoms:** What does the issue look like?
   - **Diagnosis:** How do you identify and confirm the issue?
   - **Fix:** What steps resolve the issue?
   - **Prevention/Monitoring:** How to detect early or prevent?

4. **Reference related files:**
   - Link to source code files involved
   - Reference related documentation (GUARDRAILS.md, ARCHITECTURE.md, etc.)
   - Include actual line numbers if fixing specific code

5. **Test the documentation:**
   - Verify commands work as documented
   - Test on local development environment first
   - Confirm actual file paths and endpoints are correct

**Example:** If you discover Copilot SDK health checks are failing intermittently:

1. Add to "Common Issues & Fixes" → "Issue: Copilot SDK unavailable" section
2. Document the diagnosis: What makes this different from the current issue?
3. Document the fix: New steps to resolve
4. Add debug command to "Debug Commands" → "Copilot SDK Debugging"
5. Update "Alert Thresholds" if new monitoring is needed
6. Commit with message: `docs: update RUNBOOK.md with Copilot SDK troubleshooting`

**Format Guidelines:**

- Use consistent markdown formatting
- Keep code blocks runnable (use `uv run` prefix for Python)
- Use tables for comparison/threshold data
- Include shell commands with example output
- Link to other docs when relevant
- Keep technical accuracy — this is operational documentation

See `RUNBOOK.md` for the current operational procedures and troubleshooting guide.
