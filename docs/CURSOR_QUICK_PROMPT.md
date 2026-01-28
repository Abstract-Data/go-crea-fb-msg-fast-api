# Cursor Quick Prompt: PydanticAI Gateway Migration

Copy and paste this into Cursor's chat window:

---

## PROMPT START

Refactor this project to use **PydanticAI Gateway** instead of the Copilot SDK. Follow the detailed instructions in `CURSOR_IMPLEMENTATION_PROMPT.md`.

**Summary of changes:**

1. **DELETE** `src/services/copilot_service.py` entirely

2. **UPDATE** `pyproject.toml`:
   - Change `pydantic-ai>=0.0.10` to `pydantic-ai>=1.16.0`
   - Add `pydantic-ai-slim[logfire]>=1.16.0`

3. **UPDATE** `src/config.py`:
   - Remove: `copilot_cli_host`, `copilot_enabled`
   - Add: `pydantic_ai_gateway_api_key`, `default_model`, `fallback_model`, `logfire_token`

4. **REWRITE** `src/services/agent_service.py`:
   - Use `Agent('gateway/openai:gpt-4o')` with `result_type=AgentResponse`
   - Remove all Copilot SDK dependencies
   - Add structured output support

5. **UPDATE** `src/main.py`:
   - Remove Copilot service initialization
   - Add optional Logfire instrumentation

6. **UPDATE** `src/services/reference_doc.py`:
   - Use PydanticAI Agent for document synthesis

7. **CREATE** `migrations/002_multi_tenant.sql`:
   - Add `tenants` table
   - Add `tenant_id` to existing tables
   - Add `usage_logs` table

8. **UPDATE** `.env.example` with new variables

9. **UPDATE** tests for new agent service

Read `CURSOR_IMPLEMENTATION_PROMPT.md` for complete code examples and implementation details.

Start with updating `pyproject.toml` and `src/config.py`, then proceed to rewrite `agent_service.py`.

## PROMPT END

---

## Alternative: Step-by-Step Prompts

If you prefer smaller incremental changes, use these prompts one at a time:

### Step 1: Dependencies
```
Update pyproject.toml to use pydantic-ai>=1.16.0 and add pydantic-ai-slim[logfire]>=1.16.0 for PydanticAI Gateway support.
```

### Step 2: Config
```
Update src/config.py: Remove copilot_cli_host and copilot_enabled settings. Add pydantic_ai_gateway_api_key (str), default_model (str, default "gateway/openai:gpt-4o"), fallback_model (str), and logfire_token (optional str).
```

### Step 3: Agent Service
```
Rewrite src/services/agent_service.py to use PydanticAI Agent with Gateway. Use Agent('gateway/openai:gpt-4o', result_type=AgentResponse) for structured outputs. Delete src/services/copilot_service.py. See CURSOR_IMPLEMENTATION_PROMPT.md for the full implementation.
```

### Step 4: Main App
```
Update src/main.py: Remove CopilotService initialization from lifespan. Add optional Logfire instrumentation with logfire.instrument_pydantic_ai(). Remove the copilot import.
```

### Step 5: Reference Doc
```
Update src/services/reference_doc.py to use PydanticAI Agent for document synthesis instead of CopilotService. Create a ReferenceDocument Pydantic model for structured output.
```

### Step 6: Database Migration
```
Create migrations/002_multi_tenant.sql with: tenants table (id, name, email, paig_project_id, monthly_budget_cents, plan), add tenant_id column to bot_configurations/reference_documents/message_history, create usage_logs table for cost tracking.
```

### Step 7: Tests
```
Update tests/unit/test_agent_service.py for the new PydanticAI-based MessengerAgentService. Mock the Agent class and test respond() returns AgentResponse, handles errors with escalation.
```

---

## Verification Commands

After implementation, run these to verify:

```bash
# Install updated dependencies
uv sync

# Run tests
uv run pytest -v

# Type check
uv run mypy src/

# Lint
uv run ruff check .

# Start dev server
uv run uvicorn src.main:app --reload
```
