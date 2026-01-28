[![CI](https://github.com/Abstract-Data/go-crea-fb-msg-fast-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Abstract-Data/go-crea-fb-msg-fast-api/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Abstract-Data/go-crea-fb-msg-fast-api/graph/badge.svg?token=VX987UWNEE)](https://codecov.io/gh/Abstract-Data/go-crea-fb-msg-fast-api)
[![Sentry](https://img.shields.io/badge/Sentry-enabled-green)](https://sentry.io)

# Facebook Messenger AI Bot

Production-ready FastAPI application that creates AI-powered Facebook Messenger bots. The system scrapes websites, generates a reference document using the GitHub Copilot SDK, and uses a PydanticAI agent to answer questions for people messaging a Facebook Page. This is the foundation for a turnkey product for political campaigns.

## Tech Stack

- **Backend**: FastAPI (async)
- **AI Agent**: PydanticAI with Pydantic v2 models
- **LLM Engine**: GitHub Copilot SDK (Python client)
- **Scraping**: httpx + BeautifulSoup4
- **Database**: Supabase (PostgreSQL)
- **Deployment**: Railway (FastAPI on Railway)
- **CLI**: Typer

## High-Level Architecture

```text
CLI setup (website + tone + FB config)
  ↓
Scrape website → text chunks
  ↓
Copilot SDK: synthesize "reference doc" (markdown) from chunks
  ↓
Store reference doc + config in Supabase
  ↓
PydanticAI agent uses reference doc + tone to answer questions
  ↓
FastAPI webhook receives Messenger messages, calls agent
  ↓
Send response back via Facebook Messenger API
```

## Project Structure

```text
messenger_bot/
├── src/
│   ├── main.py                # FastAPI app init
│   ├── config.py              # Settings (Pydantic BaseSettings)
│   ├── api/                   # API routes
│   ├── models/                # Pydantic models
│   ├── services/              # Business logic
│   ├── db/                    # Database layer
│   └── cli/                   # CLI commands
├── migrations/                # Database migrations
├── pyproject.toml            # Project config
├── .env.example             # Environment variables template
├── railway.toml              # Railway deployment config
└── README.md                 # This file
```

## Quick Start

### Prerequisites

- Python >= 3.12.8
- Supabase account and project
- Facebook App with Messenger permissions
- GitHub Copilot CLI (optional, falls back to OpenAI)

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run database migrations:
   ```bash
   # Apply migrations/001_initial.sql to your Supabase database
   ```
5. Start the development server:
   ```bash
   uv run uvicorn src.main:app --reload
   ```

### CLI Setup

Run the interactive setup CLI:

```bash
uv run python -m src.cli.setup_cli setup
```

This will guide you through:
1. Website URL input and scraping
2. Reference document generation via Copilot
3. Tone selection
4. Facebook Page configuration
5. Bot configuration persistence

## Environment Variables

See `.env.example` for all required environment variables:

- `FACEBOOK_PAGE_ACCESS_TOKEN` - Facebook Page access token
- `FACEBOOK_VERIFY_TOKEN` - Webhook verification token
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_KEY` - Supabase service role key
- `COPILOT_CLI_HOST` - Copilot CLI host (default: http://localhost:5909)
- `COPILOT_ENABLED` - Enable Copilot SDK (default: True)
- `OPENAI_API_KEY` - Fallback API key
- `SENTRY_DSN` - Sentry DSN for error tracking (optional)
- `SENTRY_TRACES_SAMPLE_RATE` - Sentry traces sample rate (default: 1.0)
- `ENV` - Environment (local, railway, prod)

## Deployment

### Railway Deployment

1. Connect your repository to Railway
2. Set environment variables in Railway dashboard
3. Railway will automatically detect `railway.toml` and deploy
4. The app will be available at your Railway URL

### Webhook Configuration

After deployment, configure your Facebook webhook:

1. Go to Facebook App Settings → Webhooks
2. Add webhook URL: `https://your-railway-url.railway.app/webhook`
3. Set verify token (from your `.env` file)
4. Subscribe to `messages` events

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /webhook` - Facebook webhook verification
- `POST /webhook` - Facebook message webhook

## Development

### Running Tests

```bash
uv run pytest
```

### Code Formatting

```bash
uv run ruff format .
uv run ruff check .
```
