---
name: Comprehensive Test Implementation Plan
overview: Implement comprehensive test suite for all components in src/ including unit tests, integration tests, E2E tests, property-based tests with Hypothesis, and stateful tests. Follow the testing strategy outlined in TESTING.md with emphasis on Hypothesis for validation and stateful workflows.
todos:
  - id: "1"
    content: Add test dependencies to pyproject.toml (hypothesis, pytest-cov, pytest-mock, respx, faker)
    status: completed
  - id: "2"
    content: Create tests/ directory structure with __init__.py files
    status: completed
  - id: "3"
    content: Create tests/conftest.py with shared fixtures (mock_copilot_service, mock_supabase_client, mock_httpx_client, sample data fixtures)
    status: completed
  - id: "4"
    content: Implement tests/unit/test_models.py with property-based tests for all Pydantic models
    status: completed
  - id: "5"
    content: Implement tests/unit/test_config.py for Settings validation and environment loading
    status: completed
  - id: "6"
    content: Implement tests/unit/test_scraper.py with property-based tests for chunking logic
    status: completed
  - id: "7"
    content: Implement tests/unit/test_copilot_service.py with mocked HTTP responses
    status: completed
  - id: "8"
    content: Implement tests/unit/test_agent_service.py with mocked CopilotService
    status: completed
  - id: "9"
    content: Implement tests/unit/test_facebook_service.py with mocked Facebook API
    status: completed
  - id: "10"
    content: Implement tests/unit/test_reference_doc.py with property-based hash tests
    status: completed
  - id: "11"
    content: Implement tests/unit/test_db_client.py and tests/unit/test_repository.py with mocked Supabase
    status: completed
  - id: "12"
    content: Implement tests/unit/test_setup_cli.py with mocked typer prompts and external services
    status: completed
  - id: "13"
    content: Implement tests/unit/test_hypothesis.py for additional property-based validation tests
    status: completed
  - id: "14"
    content: Implement tests/integration/ tests for service combinations
    status: completed
  - id: "15"
    content: Implement tests/stateful/test_agent_conversation.py with Hypothesis RuleBasedStateMachine
    status: completed
  - id: "16"
    content: Implement tests/stateful/test_bot_configuration.py with Hypothesis stateful testing
    status: completed
  - id: "17"
    content: Implement tests/e2e/test_health_endpoint.py and tests/e2e/test_webhook_verification.py
    status: completed
  - id: "18"
    content: Implement tests/e2e/test_webhook_message_flow.py with full message processing flow
    status: completed
  - id: "19"
    content: Implement tests/e2e/test_main.py for FastAPI app initialization and lifespan
    status: completed
  - id: "20"
    content: Configure pytest in pyproject.toml with asyncio mode, markers, and Hypothesis settings
    status: completed
  - id: "21"
    content: Run test suite and verify coverage meets goals (>90% unit, >80% integration, all critical flows covered)
    status: completed
isProject: false
---

# Comprehensive Test Implementation Plan

## Overview

This plan implements a complete test suite for all components in `src/` following the testing strategy in `TESTING.md`. The suite emphasizes property-based testing with Hypothesis for validation functions and stateful testing for workflows.

## Test Structure

Create the following test directory structure:

```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures and pytest configuration
├── unit/                          # Fast, isolated unit tests
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_scraper.py
│   ├── test_copilot_service.py
│   ├── test_agent_service.py
│   ├── test_facebook_service.py
│   ├── test_reference_doc.py
│   ├── test_db_client.py
│   ├── test_repository.py
│   └── test_hypothesis.py         # Property-based tests with Hypothesis
├── integration/                   # Service integration tests
│   ├── __init__.py
│   ├── test_agent_integration.py
│   ├── test_scraper_copilot.py
│   └── test_repository_db.py
├── e2e/                           # End-to-end API tests
│   ├── __init__.py
│   ├── test_webhook_verification.py
│   ├── test_webhook_message_flow.py
│   └── test_health_endpoint.py
└── stateful/                      # Hypothesis stateful tests
    ├── __init__.py
    ├── test_agent_conversation.py
    └── test_bot_configuration.py
```

## Dependencies to Add

Update `pyproject.toml` to include test dependencies:

- `hypothesis>=6.92.0` - Property-based and stateful testing
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.12.0` - Mocking utilities
- `httpx>=0.25.0` (already present, but needed for testing)
- `respx>=0.20.0` - HTTP mocking for httpx
- `faker>=20.0.0` - Test data generation

## Component Test Coverage

### 1. Configuration (`src/config.py`)

**File**: `tests/unit/test_config.py`

- Test `Settings` model validation
- Test environment variable loading
- Test `get_settings()` caching
- Property-based tests for settings validation with Hypothesis
- Test default values
- Test required field validation

### 2. Models (`src/models/`)

**File**: `tests/unit/test_models.py`

**Messenger Models** (`messenger.py`):

- Property-based tests for `MessengerMessageIn` with various inputs
- Test `MessengerWebhookPayload` validation
- Test edge cases (empty strings, None values, invalid types)

**Agent Models** (`agent_models.py`):

- Property-based tests for `AgentContext` with Hypothesis
- Test `AgentResponse` validation
- Test confidence score bounds (0.0-1.0)
- Test escalation logic

**Config Models** (`config_models.py`):

- Property-based tests for `BotConfiguration`
- Test `WebsiteInput` URL validation
- Test `TonePreference` validation
- Test datetime handling in `BotConfiguration`

### 3. Scraper Service (`src/services/scraper.py`)

**File**: `tests/unit/test_scraper.py`

- Test `scrape_website()` with valid URLs
- Test error handling for invalid URLs
- Test timeout handling
- Test HTML parsing and text extraction
- Test chunking logic (500-800 words per chunk)
- Property-based tests with Hypothesis:
  - Test chunking properties (all chunks are strings, non-empty)
  - Test chunk size constraints
  - Test with various HTML structures
- Test script/style/nav/footer removal
- Test whitespace normalization

### 4. Copilot Service (`src/services/copilot_service.py`)

**File**: `tests/unit/test_copilot_service.py`

- Test `is_available()` when Copilot is available
- Test `is_available()` when Copilot is unavailable
- Test `is_available()` when disabled
- Test `synthesize_reference()` with mocked Copilot responses
- Test `chat()` with mocked Copilot responses
- Test fallback to OpenAI when Copilot unavailable
- Test error handling and retries
- Test timeout handling
- Mock httpx responses for all HTTP calls

### 5. Agent Service (`src/services/agent_service.py`)

**File**: `tests/unit/test_agent_service.py`

- Test `respond()` with valid context and message
- Test system prompt construction
- Test recent messages context (last 3 messages)
- Test confidence calculation
- Test escalation logic (low confidence, "don't know" responses)
- Test response length constraints
- Property-based tests with Hypothesis:
  - Test with various message lengths
  - Test with various reference doc sizes
  - Test with different tones
- Mock CopilotService for all tests

### 6. Facebook Service (`src/services/facebook_service.py`)

**File**: `tests/unit/test_facebook_service.py`

- Test `send_message()` with valid inputs
- Test Facebook Graph API request format
- Test error handling (invalid token, network errors)
- Test timeout handling
- Mock httpx responses for Facebook API calls
- Property-based tests for message validation

### 7. Reference Doc Service (`src/services/reference_doc.py`)

**File**: `tests/unit/test_reference_doc.py`

- Test `build_reference_doc()` with valid inputs
- Test content hash generation (deterministic)
- Test hash uniqueness for different content
- Property-based tests with Hypothesis:
  - Test hash determinism (same input = same hash)
  - Test hash uniqueness (different input = different hash)
- Mock CopilotService for synthesis

### 8. Database Client (`src/db/client.py`)

**File**: `tests/unit/test_db_client.py`

- Test `get_supabase_client()` initialization
- Test client configuration from settings
- Test client reuse/caching if applicable

### 9. Repository (`src/db/repository.py`)

**File**: `tests/unit/test_repository.py`

- Test `create_reference_document()` with valid inputs
- Test `link_reference_document_to_bot()`
- Test `create_bot_configuration()` with all fields
- Test `get_bot_configuration_by_page_id()` when found
- Test `get_bot_configuration_by_page_id()` when not found
- Test `get_reference_document()` when found/not found
- Test `save_message_history()` with all fields
- Test error handling for database operations
- Mock Supabase client for all tests
- Property-based tests for data validation

### 10. API Endpoints (`src/api/`)

**Health Endpoint** (`health.py`):

- File: `tests/e2e/test_health_endpoint.py`
- Test GET `/health` returns 200
- Test response format

**Webhook Endpoint** (`webhook.py`):

- File: `tests/e2e/test_webhook_verification.py`
- Test GET `/webhook` verification with correct token
- Test GET `/webhook` verification with incorrect token
- Test missing parameters
- Test challenge response format

- File: `tests/e2e/test_webhook_message_flow.py`
- Test POST `/webhook` with valid payload
- Test message extraction from payload
- Test bot configuration lookup
- Test agent response generation
- Test Facebook message sending
- Test error handling (no bot config, invalid payload)
- Mock all external services (Supabase, Copilot, Facebook)

### 11. CLI (`src/cli/setup_cli.py`)

**File**: `tests/unit/test_setup_cli.py`

- Test interactive prompts (mock typer.prompt)
- Test website scraping step
- Test reference doc generation step
- Test tone selection
- Test Facebook config collection
- Test database persistence
- Test error handling at each step
- Mock all external calls (scraper, copilot, repository)

### 12. Main Application (`src/main.py`)

**File**: `tests/e2e/test_main.py`

- Test FastAPI app initialization
- Test lifespan startup (Supabase, Copilot initialization)
- Test lifespan shutdown
- Test CORS middleware
- Test router registration
- Test root endpoint

## Integration Tests

**File**: `tests/integration/test_agent_integration.py`

- Test agent service with real Copilot service (mocked HTTP)
- Test full flow: context → agent → response
- Test escalation scenarios

**File**: `tests/integration/test_scraper_copilot.py`

- Test scraper → Copilot synthesis flow
- Test reference doc building end-to-end

**File**: `tests/integration/test_repository_db.py`

- Test repository operations with mocked Supabase
- Test bot configuration lifecycle
- Test message history storage

## Stateful Tests (Hypothesis)

**File**: `tests/stateful/test_agent_conversation.py`

- Stateful test for agent conversation flows
- Rule: Send messages to agent
- Invariant: Response always valid, confidence in range
- Invariant: Conversation history maintains properties

**File**: `tests/stateful/test_bot_configuration.py`

- Stateful test for bot configuration operations
- Rules: Create, update, delete configurations
- Invariant: No duplicate page_ids
- Invariant: Deleted configs not in active set

## Test Fixtures (`tests/conftest.py`)

Create shared fixtures:

- `mock_copilot_service` - Mock CopilotService
- `mock_supabase_client` - Mock Supabase client
- `mock_httpx_client` - Mock httpx for HTTP calls
- `sample_bot_config` - Sample bot configuration dict
- `sample_reference_doc` - Sample reference document
- `sample_agent_context` - Sample AgentContext
- `test_client` - FastAPI TestClient
- `mock_facebook_api` - Mock Facebook Graph API responses

## Pytest Configuration

Create `pytest.ini` or add to `pyproject.toml`:

- Configure asyncio mode
- Set test paths
- Configure Hypothesis settings
- Set coverage options
- Configure markers (unit, integration, e2e, stateful)

## Coverage Goals

- Unit tests: > 90% coverage for services and utilities
- Property-based tests: All validation and transformation functions
- Stateful tests: All stateful workflows
- Integration tests: > 80% coverage for service combinations
- E2E tests: Cover all critical user flows

## Implementation Order

1. Add test dependencies to `pyproject.toml`
2. Create test directory structure
3. Create `conftest.py` with shared fixtures
4. Implement unit tests for models (foundation)
5. Implement unit tests for services (core logic)
6. Implement unit tests for API endpoints
7. Implement property-based tests with Hypothesis
8. Implement integration tests
9. Implement stateful tests with Hypothesis
10. Implement E2E tests
11. Configure pytest and coverage reporting
12. Verify all tests pass and coverage meets goals