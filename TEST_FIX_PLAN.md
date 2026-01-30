# Test Fix Plan

## Summary
30 tests failing, 94 passing, 2 skipped

## Issue Categories

### 1. E2E Tests (19 failures)
**Root Cause**: Settings validation requires `pydantic_ai_gateway_api_key` but test mocks don't include it.

**Affected Files**:
- `tests/e2e/test_health_endpoint.py` (3 tests)
- `tests/e2e/test_main.py` (6 tests)
- `tests/e2e/test_webhook_message_flow.py` (4 tests)
- `tests/e2e/test_webhook_verification.py` (5 tests)

**Fix**: Add `pydantic_ai_gateway_api_key="paig_test_key"` to all Settings() instantiations in e2e tests.

### 2. Stateful Tests (2 failures)
**Root Cause**: Same as E2E - missing `pydantic_ai_gateway_api_key` in Settings.

**Affected Files**:
- `tests/stateful/test_agent_conversation.py` (2 tests)

**Fix**: Add `pydantic_ai_gateway_api_key` to Settings or mock `get_settings()` properly.

### 3. Facebook Service Tests (4 failures)
**Root Cause**: `request.read()` doesn't work with respx mock - need to use `request.content` or access JSON payload directly.

**Affected Tests**:
- `test_send_message_request_format`
- `test_send_message_properties`
- `test_send_message_access_token_in_params`
- `test_send_message_long_text`

**Fix**: Replace `json.loads(request.read())` with `json.loads(request.content)` or use respx's request capture methods.

### 4. Logging Tests (6 failures)

#### 4a. Agent Service Logging (1 failure)
**Root Cause**: `MessengerAgentService()` initialization requires `PYDANTIC_AI_GATEWAY_API_KEY` env var.

**Fix**: Set env var in test or mock `get_settings()` to return valid settings.

#### 4b. Scraper Logging (1 failure)
**Root Cause**: `respx_mock.get()` returns string instead of `httpx.Response` object.

**Fix**: Change mock to return `httpx.Response(200, text="...")` instead of just string.

#### 4c. Facebook Service Logging (1 failure)
**Root Cause**: Same as 4b - respx_mock returns dict instead of `httpx.Response`.

**Fix**: Change mock to return `httpx.Response(200, json={...})`.

#### 4d. Repository Logging (3 failures)
**Root Cause**: Supabase client initialization fails with "Invalid URL" - mock_supabase_client fixture needs proper URL setup.

**Affected Tests**:
- `test_repository_logs_document_creation`
- `test_repository_logs_bot_config_lookup`
- `test_repository_logs_message_history_save`

**Fix**: Ensure mock_supabase_client doesn't trigger URL validation, or provide valid URL in Settings mock.

## Implementation Order

1. Fix Settings mocks (E2E + Stateful) - Quick wins
2. Fix Facebook service request reading - Medium complexity
3. Fix logging test mocks - Medium complexity
4. Fix repository logging tests - May need fixture updates

## Verification

After fixes, run:
```bash
uv run pytest -v
```

Expected: All 126 tests should pass (or skip if intentionally skipped).
