# RUNBOOK.md

Quick reference for common issues, fixes, and troubleshooting procedures for the Facebook Messenger AI Bot.

_This runbook should be updated whenever new issues are discovered or procedures change. Keep it synchronized with the codebase and operational reality. See `AGENTS.md` and `TESTING.md` for instructions on when and how to update this runbook._

---

## Common Issues & Fixes

### Issue: Agent returns off-topic responses

**Symptoms:**
- Agent responses are not based on the reference document
- Agent provides information outside the knowledge base
- High escalation rate due to out-of-scope queries

**Diagnosis:**
1. Check agent confidence scores in Logfire logs:
   ```bash
   # If using Logfire cloud: View logs in Logfire dashboard
   # If local: Check structured logs for confidence scores
   grep -i "confidence" logs/*.log | grep -E "confidence=[0-9.]+"
   ```
2. Review agent service logs for low confidence patterns:
   ```bash
   grep "low confidence\|escalat\|requires_escalation" logs/*.log
   ```
3. Check reference document is properly loaded:
   ```bash
   uv run python -m src.cli.setup_cli verify  # If CLI has verify command
   ```

**Fix:**
1. Review reference document content for completeness
2. Update reference document if source website changed:
   - Re-run CLI setup: `uv run python -m src.cli.setup_cli setup`
   - Or manually update via Supabase dashboard
3. Verify agent system prompt in `src/services/agent_service.py` line 49
4. Adjust confidence threshold (currently 0.7) in agent logic if needed
5. Test with evaluation set:
   ```bash
   uv run pytest tests/e2e/test_webhook_message_flow.py -v
   ```

---

### Issue: Copilot SDK unavailable / fallback to OpenAI

**Symptoms:**
- Health check returns non-200 status
- Response latency increases significantly
- Fallback to OpenAI is being used frequently

**Diagnosis:**
1. Check Copilot SDK availability:
   ```bash
   curl -X GET http://localhost:5909/health -v
   ```
2. Check if Copilot CLI is running:
   ```bash
   ps aux | grep copilot
   ```
3. Review Logfire logs for health check failures:
   ```bash
   # Search for Copilot health check logs
   grep -i "copilot.*health\|copilot.*available\|copilot.*unavailable" logs/*.log
   # Or check Logfire dashboard for structured logs with correlation IDs
   ```
4. Check Copilot service logs in `src/services/copilot_service.py` initialization

**Fix:**
1. Verify GitHub Copilot CLI is installed:
   ```bash
   github-copilot --version
   ```
2. Start Copilot CLI if not running:
   ```bash
   github-copilot-cli start
   ```
3. Check COPILOT_CLI_HOST environment variable:
   ```bash
   echo $COPILOT_CLI_HOST
   ```
4. Verify port 5909 is not blocked:
   ```bash
   lsof -i :5909
   ```
5. Restart the FastAPI application if health check still fails
6. Monitor fallback rate - if > 5%, investigate Copilot CLI stability

---

### Issue: Facebook API errors / rate limiting

**Symptoms:**
- Messages not being sent to users
- HTTP 429 (Too Many Requests) errors
- HTTP 401 (Unauthorized) errors
- HTTP 403 (Forbidden) errors

**Diagnosis:**
1. Check Facebook API response in logs:
   ```bash
   grep "facebook_service\|send_message" logs/*.log | grep -i "error\|429\|401\|403"
   ```
2. Verify Facebook page access token:
   ```bash
   echo $FACEBOOK_PAGE_ACCESS_TOKEN | wc -c  # Should be ~100+ characters
   ```
3. Check token expiration with Facebook Graph API:
   ```bash
   curl "https://graph.facebook.com/v18.0/debug_token?input_token={token}&access_token={token}"
   ```
4. Check rate limit status:
   ```bash
   grep "rate_limit\|429" logs/*.log
   ```

**Fix:**
1. **For 401/403 errors (invalid or expired token):**
   - Generate new page access token from Facebook App Dashboard
   - Update FACEBOOK_PAGE_ACCESS_TOKEN in Railway environment
   - Restart application

2. **For 429 errors (rate limiting):**
   - Implement exponential backoff (already done in `src/services/facebook_service.py`)
   - Reduce concurrent message sends if applicable
   - Check if another process is sending messages on same page
   - Contact Facebook support if limit is too restrictive

3. **For other HTTP errors:**
   - Check Facebook API documentation for error codes
   - Verify page ID and recipient IDs are correct
   - Check message content (too long, invalid format)

---

### Issue: Database connection failures

**Symptoms:**
- "Failed to connect to database" errors
- Queries timing out
- Connection pool exhausted errors
- 500 Internal Server Error on webhook requests

**Diagnosis:**
1. Check Supabase connection status:
   ```bash
   curl -X POST https://<supabase-url>/rest/v1/rpc/health_check \
     -H "apikey: $SUPABASE_SERVICE_KEY"
   ```
2. Verify Supabase credentials:
   ```bash
   echo "URL: $SUPABASE_URL"
   echo "KEY length: ${#SUPABASE_SERVICE_KEY}"
   ```
3. Check database connection logs:
   ```bash
   grep "database\|connection\|timeout" logs/*.log | grep -i error
   ```
4. Verify network connectivity:
   ```bash
   ping <supabase-url>
   ```

**Fix:**
1. Verify SUPABASE_URL and SUPABASE_SERVICE_KEY in environment:
   ```bash
   # In Railway dashboard: Settings → Environment
   ```
2. Check Supabase project status in Supabase dashboard
3. Restart application to refresh connection pool:
   ```bash
   # In Railway: Deployment → Restart
   ```
4. Check if connection pool is exhausted:
   - Review repository.py connection pooling settings
   - May need to increase pool size if high concurrency
5. Check for long-running queries blocking connections
6. Review Supabase logs in Supabase dashboard for errors

---

### Issue: Low confidence scores / high escalation rates

**Symptoms:**
- Escalation rate > 20% (alert threshold)
- Agent confidence consistently < 0.7
- Many messages being routed to human review

**Diagnosis:**
1. Check escalation rate in logs:
   ```bash
   grep "requires_escalation" logs/*.log | grep true | wc -l
   ```
2. Review escalation reasons:
   ```bash
   grep "escalation_reason" logs/*.log
   ```
3. Analyze confidence score distribution:
   ```bash
   grep "confidence" logs/*.log | cut -d= -f2 | sort -n | tail -20
   ```
4. Check if reference document is empty or corrupted:
   ```bash
   # Via Supabase: SELECT * FROM reference_documents LIMIT 1;
   ```

**Fix:**
1. **If reference document is incomplete:**
   - Run setup again: `uv run python -m src.cli.setup_cli setup`
   - Verify website is still accessible and content is relevant
   - Check for website structure changes

2. **If confidence threshold is too strict:**
   - Review current threshold (0.7) in `src/services/agent_service.py` line 57
   - Consider lowering if threshold is unreasonably high
   - Document any changes to RUNBOOK.md

3. **If question types are out of scope:**
   - Update agent system prompt with new use cases
   - Add examples to the agent context
   - Review GUARDRAILS.md for escalation rules

4. **Monitor after changes:**
   ```bash
   uv run pytest tests/integration/test_agent_integration.py -v
   ```

---

### Issue: Message processing failures

**Symptoms:**
- Webhook returns 200 but message not processed
- Agent service times out
- Message appears in logs but no response sent

**Diagnosis:**
1. Check webhook processing logs:
   ```bash
   grep "POST /webhook\|process_message" logs/*.log
   ```
2. Verify message payload format:
   ```bash
   grep "MessengerWebhookPayload" logs/*.log | grep -i error
   ```
3. Check for async task completion:
   ```bash
   grep "background_task\|BackgroundTasks" logs/*.log
   ```
4. Check agent service performance:
   ```bash
   grep "Agent response latency\|timeout" logs/*.log
   ```

**Fix:**
1. Verify webhook payload is valid JSON:
   - Check Facebook webhook documentation
   - Test with manual webhook call: `uv run pytest tests/e2e/test_webhook_verification.py`

2. Check agent service latency:
   - If > 2s, investigate Copilot SDK response time
   - May need to increase timeouts in config

3. Verify background tasks are completing:
   - Check FastAPI app state: `app.state.background_tasks`
   - Ensure no unhandled exceptions in task

4. Review message processing flow in `src/api/webhook.py`

---

### Issue: Webhook verification fails

**Symptoms:**
- Facebook webhook setup fails during verification
- 403 Forbidden on GET /webhook
- Facebook shows "Webhook URL couldn't be validated"

**Diagnosis:**
1. Check verify token:
   ```bash
   echo $FACEBOOK_VERIFY_TOKEN
   ```
2. Check webhook endpoint is responding:
   ```bash
   curl -X GET "http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=test&hub.verify_token=$FACEBOOK_VERIFY_TOKEN"
   ```
3. Check webhook logs:
   ```bash
   grep "verify_webhook\|webhook verification" logs/*.log
   ```

**Fix:**
1. Verify FACEBOOK_VERIFY_TOKEN matches in both:
   - `.env` file locally
   - Railway environment variables
   - Facebook App Webhook Settings

2. Ensure webhook URL is publicly accessible:
   - Railway URL should be: `https://<railway-url>/webhook`
   - Test with curl from another machine

3. Check webhook endpoint code in `src/api/webhook.py`:
   - Verify verification logic is correct
   - Ensure token comparison is exact (case-sensitive)

4. Test webhook verification:
   ```bash
   uv run pytest tests/e2e/test_webhook_verification.py -v
   ```

---

## Debug Commands

### Health Checks

```bash
# Check application health
curl http://localhost:8000/health

# Check Copilot SDK health
curl http://localhost:5909/health

# Check Supabase connection
curl -X POST https://<supabase-url>/rest/v1/rpc/health_check \
  -H "apikey: $SUPABASE_SERVICE_KEY"

# Check Facebook API connectivity
curl "https://graph.facebook.com/v18.0/me?access_token=$FACEBOOK_PAGE_ACCESS_TOKEN"
```

### Viewing Logs

**Local Development (Console Logs):**
```bash
# View application logs with debug level
LOG_LEVEL=DEBUG uv run uvicorn src.main:app --reload

# Search logs for errors
grep -i error logs/*.log

# Search logs for specific service
grep "CopilotService\|FacebookService\|AgentService" logs/*.log

# Filter by log level
grep "\[ERROR\]\|\[WARNING\]" logs/*.log

# Real-time log monitoring
tail -f logs/*.log
```

**Logfire Structured Logs:**
```bash
# Logfire automatically instruments FastAPI, Pydantic, and services
# All logs are structured with correlation IDs for request tracing

# Search for correlation IDs to trace a request
grep "correlation_id" logs/*.log

# View request/response traces
grep "POST /webhook\|GET /health" logs/*.log

# View agent execution traces
grep "Processing agent response\|Agent response generated" logs/*.log

# View database operation timing
grep "database_query\|query_duration" logs/*.log

# If using Logfire cloud (with LOGFIRE_TOKEN set):
# - View logs in Logfire dashboard
# - Use correlation IDs to trace complete request flows
# - Filter by service, log level, or time range
```

### Database Queries

```bash
# Connect to Supabase (via Supabase CLI)
supabase db pull

# Query bot configurations
# Via Supabase dashboard: SELECT * FROM bot_configurations;

# Query recent messages
# Via Supabase dashboard: SELECT * FROM message_history ORDER BY created_at DESC LIMIT 100;

# Query reference documents
# Via Supabase dashboard: SELECT id, bot_config_id, LENGTH(content) as content_size FROM reference_documents;
```

### Test REPL conversation persistence

Test conversations from **Test the bot** (in-flow) or **`uv run python -m src.cli.setup_cli test`** are stored in Supabase.

- **Tables:** `test_sessions` (one per REPL run: `reference_doc_id`, `source_url`, `tone`) and `test_messages` (each user/bot exchange).
- **Session ID:** When a test REPL starts, the CLI prints `Session ID: <uuid> — view in Supabase: test_sessions / test_messages`. Use that UUID to filter.
- **View in Supabase:** Open Table Editor (or SQL) → `test_sessions` for config, `test_messages` for history. Filter `test_messages` by `test_session_id` = the echoed session ID to see the current run.
- If Supabase is unavailable during a test run, the CLI warns and the REPL continues without persisting.

### Agent Service Debugging

```bash
# Run agent with debug output
LOG_LEVEL=DEBUG uv run uvicorn src.main:app --reload

# Test agent with sample message
uv run python -c "
from src.services.agent_service import MessengerAgentService
from src.services.copilot_service import CopilotService
from src.models.agent_models import AgentContext
import asyncio

async def test():
    copilot = CopilotService('http://localhost:5909')
    agent = MessengerAgentService(copilot)
    context = AgentContext(
        bot_config_id='test-123',
        reference_doc='# Test\nThis is a test document.',
        tone='professional',
        recent_messages=[]
    )
    response = await agent.respond(context, 'What is this about?')
    print(f'Response: {response}')

asyncio.run(test())
"

# Run evaluation tests
uv run pytest tests/unit/test_agent_service.py -v --hypothesis-show-statistics

# View agent execution traces in Logfire
grep -i "processing agent response\|agent response generated\|confidence\|escalation" logs/*.log

# Trace a specific request by correlation ID
# (Get correlation_id from webhook logs, then search)
grep "correlation_id=<id>" logs/*.log
```

### Copilot SDK Debugging

```bash
# Check Copilot SDK status
uv run python -c "
from src.services.copilot_service import CopilotService
import asyncio

async def check():
    copilot = CopilotService('http://localhost:5909')
    available = await copilot.is_available()
    print(f'Copilot available: {available}')

asyncio.run(check())
"

# Test Copilot fallback to OpenAI
COPILOT_ENABLED=false uv run uvicorn src.main:app

# Monitor Copilot response times in Logfire logs
grep -i "copilot.*response\|copilot.*timing\|copilot.*duration" logs/*.log

# Check for fallback events
grep -i "fallback.*openai\|using.*openai.*fallback" logs/*.log

# View Copilot health check logs
grep -i "copilot.*health\|copilot.*available" logs/*.log
```

### Facebook API Testing

```bash
# Test webhook by sending test message
uv run pytest tests/e2e/test_webhook_message_flow.py -v

# Verify page token is valid
curl "https://graph.facebook.com/v18.0/debug_token?input_token=$FACEBOOK_PAGE_ACCESS_TOKEN&access_token=$FACEBOOK_PAGE_ACCESS_TOKEN"

# Send test message to Facebook
curl -X POST https://graph.facebook.com/v18.0/me/messages \
  -H "Content-Type: application/json" \
  -d "{
    \"recipient\": {\"id\": \"<user_id>\"},
    \"message\": {\"text\": \"Test message\"}
  }" \
  -d "access_token=$FACEBOOK_PAGE_ACCESS_TOKEN"
```

### Testing & Coverage

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=term-missing

# Run specific test category
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
uv run pytest tests/e2e/ -v

# Run Hypothesis tests with statistics
uv run pytest tests/unit/test_hypothesis.py -v --hypothesis-show-statistics

# Run stateful tests
uv run pytest tests/stateful/ -v
```

---

## Alert Thresholds

| Alert | Threshold | Action | Monitoring |
|-------|-----------|--------|------------|
| Response Latency (p95) | > 2 seconds | Investigate Copilot SDK or database | Check Logfire traces for `agent_response_latency_seconds` or request timing |
| Error Rate | > 2% for 5 min | Page on-call engineer | Monitor HTTP 5xx errors in Logfire logs or Sentry |
| Escalation Rate | > 20% | Review agent prompt & reference doc | Count `requires_escalation=true` in Logfire logs |
| Copilot SDK Availability | < 99% uptime | Restart Copilot CLI or fallback to OpenAI | Monitor health check frequency in Logfire logs |
| Copilot Fallback Rate | > 5% | Investigate Copilot SDK stability | Count OpenAI fallback events in Logfire logs |
| Facebook API Error Rate | > 10% (any HTTP error) | Check token/rate limits | Monitor HTTP errors in Logfire `facebook_service` logs |
| Database Connection Failures | > 3 consecutive | Restart app or check Supabase | Monitor connection timeouts in Logfire logs |
| Message Processing Timeout | > 30 seconds | Investigate bottleneck (Copilot, DB, FB API) | Check task processing latency in Logfire traces |
| Logfire Logging Failures | Any | Check Logfire configuration | Monitor for missing correlation IDs or structured log format issues |

---

## Service-Specific Troubleshooting

### CopilotService (`src/services/copilot_service.py`)

**Health Check:**
```bash
curl http://localhost:5909/health
```

**Common Issues:**
- **Service unavailable:** Check Copilot CLI is running, port 5909 is accessible
- **Timeout errors:** Increase timeout (default 2 seconds) in `is_available()` method
- **Fallback behavior:** Automatically uses OpenAI when unavailable, logged with `logfire.info()`

**Fallback Logic:**
- If `is_available()` returns False, agent uses OpenAI instead of Copilot
- Fallback is logged with structured Logfire logs, monitor with: `grep -i "fallback.*openai\|using.*openai.*fallback" logs/*.log`
- Logfire traces include timing, health check status, and fallback events with correlation IDs

**Logfire Logging:**
- Health check timing and availability status logged
- API call success/failure with response times
- Fallback events include context (reason, timing, response)
- All logs include correlation IDs for request tracing

---

### MessengerAgentService (`src/services/agent_service.py`)

**Common Issues:**
- **Low confidence scores:** Reference document incomplete or question out of scope
- **Off-topic responses:** Agent system prompt needs examples of in-scope queries
- **Response too long:** Responses are truncated to 300 characters (Facebook Messenger limit)
- **Escalation loops:** Check escalation reason in logs

**Debugging:**
- Add debug output: `LOG_LEVEL=DEBUG` in environment
- Review agent logs: `grep -i "messenger.*agent\|processing agent response\|agent response generated" logs/*.log`
- Check confidence threshold: Currently 0.7 in `respond()` method
- View structured Logfire logs for confidence scores, escalation decisions, and timing
- Trace complete request flow using correlation IDs from Logfire logs

---

### FacebookService (`src/services/facebook_service.py`)

**Common Issues:**
- **401 Unauthorized:** Token expired or invalid
- **429 Rate Limited:** Too many requests in short time
- **400 Bad Request:** Message format invalid or recipient ID wrong

**Debugging:**
```bash
# Check token validity
curl "https://graph.facebook.com/v18.0/me?access_token=$FACEBOOK_PAGE_ACCESS_TOKEN"

# Test message send
curl -X POST https://graph.facebook.com/v18.0/me/messages \
  -d "access_token=$FACEBOOK_PAGE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"recipient":{"id":"<user_id>"},"message":{"text":"test"}}'
```

**Retry Logic:**
- Implements exponential backoff (max 3 retries)
- Check retry logs: `grep "retry\|backoff" logs/*.log`

---

### ScraperService (`src/services/scraper.py`)

**Common Issues:**
- **Timeout errors:** Website too slow, network issues
- **Parse errors:** HTML structure changed or unexpected format
- **Empty content:** Website blocks scraping or content not found

**Debugging:**
```bash
# Test scraping manually
uv run python -c "
from src.services.scraper import scrape_website
import asyncio

async def test():
    chunks = await scrape_website('https://example.com')
    print(f'Chunks: {len(chunks)}')

asyncio.run(test())
"

# Check scraper logs
grep "ScraperService\|scrape_website\|chunk" logs/*.log
```

---

### Repository (`src/db/repository.py`)

**Common Issues:**
- **Connection pool exhausted:** Too many concurrent requests
- **Query timeouts:** Large dataset or slow query
- **Foreign key constraints:** Data integrity issues

**Debugging:**
```bash
# Check active connections in Supabase dashboard
# Settings → Database → Connections

# Monitor query performance in Logfire logs
grep -i "database.*query\|query.*duration\|database.*timing" logs/*.log

# Check for connection pool issues
grep -i "pool.*exhausted\|connection.*failed\|database.*error" logs/*.log

# View database operation traces with correlation IDs
grep "correlation_id" logs/*.log | grep -i "database\|repository"
```

**Logfire Logging:**
- Database operation timing logged for all queries
- Query success/failure rates tracked
- Bot configuration lookups include timing
- Message history storage metrics logged
- All operations include correlation IDs for request tracing

### Logfire Observability (`src/logging_config.py`)

**Configuration:**
- Centralized logging setup in `src/logging_config.py`
- Environment-aware: Console formatting for local, JSON for production
- FastAPI and Pydantic instrumentation enabled automatically
- Optional cloud logging with `LOGFIRE_TOKEN` environment variable

**Common Issues:**
- **Logs not appearing:** Check `LOG_LEVEL` environment variable (default: INFO)
- **Missing correlation IDs:** Ensure `CorrelationIDMiddleware` is first middleware
- **PII in logs:** Verify `logfire_enable_pii_masking=True` in settings
- **Cloud logging not working:** Check `LOGFIRE_TOKEN` is set correctly

**Debugging:**
```bash
# Check Logfire configuration
uv run python -c "
from src.config import get_settings
settings = get_settings()
print(f'Log Level: {settings.log_level}')
print(f'PII Masking: {settings.logfire_enable_pii_masking}')
print(f'Request Logging: {settings.logfire_enable_request_logging}')
print(f'Logfire Token Set: {bool(settings.logfire_token)}')
"

# Verify Logfire initialization
grep -i "logfire.*configure\|logfire.*initialized" logs/*.log

# Check for correlation IDs in logs
grep "correlation_id" logs/*.log | head -5

# View structured log format
tail -20 logs/*.log | grep -v "^$"
```

**Logfire Features:**
- **Request Tracing:** Automatic FastAPI request/response tracing with timing
- **Pydantic Validation:** Model validation errors logged automatically
- **PydanticAI Tracing:** Agent execution and decision logging
- **Correlation IDs:** Request tracing across all services
- **Structured Logs:** JSON format in production for log aggregation
- **PII Masking:** Automatic masking of sensitive data (tokens, PII)

---

## Quick Reference

### Environment Variable Checklist

```bash
# Required variables (will fail without these)
✓ FACEBOOK_PAGE_ACCESS_TOKEN    # Long-lived page token
✓ FACEBOOK_VERIFY_TOKEN         # Custom webhook token
✓ SUPABASE_URL                  # Supabase project URL
✓ SUPABASE_SERVICE_KEY          # Service role key

# Optional but recommended
✓ COPILOT_CLI_HOST              # Default: http://localhost:5909
✓ COPILOT_ENABLED               # Default: True
✓ OPENAI_API_KEY                # Fallback LLM
✓ LOGFIRE_TOKEN                 # Logfire cloud logging (optional, enables cloud dashboard)
✓ LOG_LEVEL                     # Default: INFO (DEBUG, INFO, WARNING, ERROR, CRITICAL)
✓ LOGFIRE_ENABLE_PII_MASKING    # Default: True (mask sensitive data in logs)
✓ LOGFIRE_ENABLE_REQUEST_LOGGING # Default: True (HTTP request/response logging)
✓ SENTRY_DSN                    # Error tracking (optional)

# Check all are set
env | grep -i facebook
env | grep -i supabase
env | grep -i copilot
env | grep -i openai
```

### Common Error Messages & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "Failed to connect to Supabase" | Invalid credentials or network issue | Verify SUPABASE_URL and SUPABASE_SERVICE_KEY |
| "Copilot SDK unavailable, using OpenAI fallback" | Copilot CLI not running or unreachable | Start GitHub Copilot CLI: `github-copilot-cli start` |
| "Facebook API returned 401" | Invalid or expired token | Generate new page access token in Facebook App |
| "Webhook verification failed" | Token mismatch | Verify FACEBOOK_VERIFY_TOKEN matches Facebook settings |
| "Agent confidence too low" | Question out of scope or poor reference doc | Review reference document and update if needed |
| "Database connection timeout" | Connection pool exhausted or network issue | Restart app or check Supabase status |
| "Logfire configuration failed" | Invalid Logfire token or network issue | Verify LOGFIRE_TOKEN (if using cloud) or check local logging setup |
| "Missing correlation ID in logs" | CorrelationIDMiddleware not properly configured | Ensure middleware is added first in `src/main.py` |
| "PII detected in logs" | PII masking disabled or misconfigured | Set `LOGFIRE_ENABLE_PII_MASKING=True` and verify `mask_pii()` usage |

### Deployment Verification Steps

1. **Pre-deployment checklist:**
   ```bash
   # Format code
   uv run ruff format .
   
   # Run linter
   uv run ruff check .
   
   # Run all tests
   uv run pytest --cov=src --cov-report=term-missing
   ```

2. **Post-deployment (on Railway):**
   ```bash
   # Health check
   curl https://<railway-url>/health
   
   # Verify webhook endpoint
   curl https://<railway-url>/webhook?hub.mode=subscribe&hub.verify_token=test&hub.challenge=test123
   ```

3. **Environment variable verification:**
   - Check Railway Environment variables are set
   - Verify no secrets in logs: `grep -i token logs/*.log` (should show masked tokens if PII masking enabled)
   - Verify Logfire configuration: Check `LOG_LEVEL`, `LOGFIRE_TOKEN` (if using cloud), `LOGFIRE_ENABLE_PII_MASKING`

### Webhook Configuration Verification

1. **Facebook App Setup:**
   - Go to Facebook App → Messenger → Settings
   - Webhook URL: `https://<railway-url>/webhook`
   - Verify Token: Matches FACEBOOK_VERIFY_TOKEN
   - Subscribe to: `messages`, `messaging_postbacks`

2. **Test Webhook:**
   ```bash
   # Local testing
   curl -X POST http://localhost:8000/webhook \
     -H "Content-Type: application/json" \
     -d '{"object":"page","entry":[{"messaging":[{"sender":{"id":"test"},"message":{"text":"hello"}}]}]}'
   ```

3. **Verify in Facebook:**
   - Check webhook status in App Dashboard
   - Should show "Verified" status
   - Review recent requests/errors

---

## Maintenance

This runbook is a living document and should be updated when:

1. **New operational issues are discovered** — Add to "Common Issues & Fixes" section
2. **New debugging procedures are developed** — Add to "Debug Commands" section
3. **New alert thresholds are established** — Update "Alert Thresholds" table
4. **Service behavior changes** — Update "Service-Specific Troubleshooting" section
5. **Environment or deployment changes** — Update relevant sections

**For instructions on when and how to update this runbook, see:**
- `AGENTS.md` — "Operational Documentation Maintenance" section
- `TESTING.md` — "Operational Issue Documentation" section

---
