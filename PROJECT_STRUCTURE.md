# Project Structure

## Overview

Complete directory structure for the Facebook Messenger AI Bot project with explanations of each file and directory.

## Directory Tree

```text
messenger_bot/
├── src/
│   ├── __init__.py           # Package initialization
│   ├── main.py               # FastAPI app initialization
│   ├── config.py             # Settings (Pydantic BaseSettings)
│   ├── api/                  # API routes and endpoints
│   │   ├── __init__.py
│   │   ├── webhook.py         # Facebook webhook endpoints
│   │   ├── setup.py           # HTTP setup endpoints (optional)
│   │   └── health.py          # /health for Railway
│   ├── models/                # Pydantic models for data validation
│   │   ├── __init__.py
│   │   ├── messenger.py       # Incoming/outgoing FB models
│   │   ├── config_models.py   # Bot + FB config models
│   │   └── agent_models.py    # AgentContext, AgentResponse
│   ├── services/              # Business logic and service layer
│   │   ├── __init__.py
│   │   ├── scraper.py         # Website scraping & chunking
│   │   ├── copilot_service.py # Copilot SDK wrapper
│   │   ├── reference_doc.py   # Build reference doc via Copilot
│   │   ├── agent_service.py   # PydanticAI agent
│   │   └── facebook_service.py # Send messages to FB Graph API
│   ├── db/                    # Database client and repository
│   │   ├── __init__.py
│   │   ├── client.py          # Supabase client
│   │   └── repository.py      # Bot config / message history
│   └── cli/                   # CLI commands for setup
│       ├── __init__.py
│       └── setup_cli.py       # Typer-based interactive setup
├── migrations/                # Database migrations
│   └── 001_initial.sql        # Initial schema
├── pyproject.toml             # Project configuration
├── .env.example              # Environment variables template
├── railway.toml              # Railway deployment config
└── README.md                  # Project documentation
```

## File Descriptions

### Root Level

- **pyproject.toml**: Python project configuration, dependencies, and build system
- **.env.example**: Template for environment variables
- **railway.toml**: Railway deployment configuration
- **README.md**: Project documentation
- **PROJECT_STRUCTURE.md**: This file

### src/ Directory

Main application package.

#### src/main.py

FastAPI application initialization:
- Creates FastAPI app instance
- Registers routers (webhook, health, setup)
- Startup event handlers (Supabase init, Copilot check)
- Uvicorn configuration for Railway

#### src/config.py

Application configuration using Pydantic BaseSettings:
- Loads environment variables
- Provides type-safe settings access
- Includes `get_settings()` helper with `lru_cache()`

### src/api/ Directory

API routes and endpoints.

#### src/api/webhook.py

Facebook webhook endpoints:
- `GET /webhook`: Webhook verification
- `POST /webhook`: Message event handling

#### src/api/health.py

Health check endpoint:
- `GET /health`: Returns `{status: "ok"}` for Railway

#### src/api/setup.py

Optional HTTP setup endpoints (alternative to CLI).

### src/models/ Directory

Pydantic models for data validation.

#### src/models/messenger.py

Facebook Messenger models:
- `MessengerEntry`: Webhook entry
- `MessengerMessageIn`: Incoming message
- `MessengerWebhookPayload`: Full webhook payload

#### src/models/config_models.py

Configuration models:
- `WebsiteInput`: Website URL input
- `TonePreference`: Communication tone
- `FacebookConfig`: Facebook app configuration
- `BotConfiguration`: Complete bot configuration

#### src/models/agent_models.py

Agent models:
- `AgentContext`: Context for agent responses
- `AgentResponse`: Agent response with confidence

### src/services/ Directory

Business logic and service layer.

#### src/services/scraper.py

Website scraping service:
- Uses `httpx.AsyncClient` for async requests
- Parses HTML with BeautifulSoup
- Chunks text into 500-800 word segments

#### src/services/copilot_service.py

GitHub Copilot SDK wrapper:
- Async wrapper over Copilot SDK runtime
- Fallback to OpenAI when unavailable
- Methods: `is_available()`, `synthesize_reference()`, `chat()`

#### src/services/reference_doc.py

Reference document builder:
- Uses Copilot to synthesize markdown from chunks
- Stores in `reference_documents` table

#### src/services/agent_service.py

PydanticAI agent service:
- Builds system prompt with reference doc and tone
- Returns typed `AgentResponse`
- Handles message context

#### src/services/facebook_service.py

Facebook Graph API wrapper:
- Sends messages via `me/messages` endpoint
- Uses page access token

### src/db/ Directory

Database client and repository layer.

#### src/db/client.py

Supabase client initialization:
- Creates and configures Supabase client
- Handles connection management

#### src/db/repository.py

Database repository:
- Bot configuration CRUD operations
- Message history storage
- Reference document queries

### src/cli/ Directory

CLI commands for setup and management.

#### src/cli/setup_cli.py

Interactive setup CLI using Typer:
- Website URL input and validation
- Scraping and reference doc generation
- Tone selection
- Facebook configuration
- Bot persistence

### migrations/ Directory

Database migration files:
- **001_initial.sql**: Initial schema with all tables, indexes, and triggers

## Import Path Examples

```python
# From src/main.py
from src.api import webhook, health
from src.config import get_settings
from src.db.client import get_supabase_client

# From services
from src.services.scraper import scrape_website
from src.services.copilot_service import CopilotService
from src.services.agent_service import MessengerAgentService

# From models
from src.models.messenger import MessengerWebhookPayload
from src.models.config_models import BotConfiguration
from src.models.agent_models import AgentContext, AgentResponse
```
