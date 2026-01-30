# Pydantic Logfire Integration Guide

This project uses [Pydantic Logfire](https://logfire.pydantic.dev/) for comprehensive observability, including structured logging, request tracing, and performance monitoring.

## Overview

Logfire provides:
- **Structured JSON logging** for production log aggregation
- **Request tracing** with correlation IDs across services
- **Performance monitoring** with automatic timing metrics
- **FastAPI instrumentation** for automatic request/response logging
- **Pydantic instrumentation** for model validation logging
- **PII masking** for security and compliance

## Setup

### 1. Install Dependencies

Logfire is already included in `pyproject.toml`:

```toml
"logfire[fastapi,pydantic]>=1.0.0"
```

Install with:
```bash
uv sync
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Optional: Cloud logging token (get from https://logfire.pydantic.dev/)
LOGFIRE_TOKEN=your_logfire_token_here

# Logging level
LOG_LEVEL=INFO

# Enable PII masking (recommended for production)
LOGFIRE_ENABLE_PII_MASKING=True

# Enable HTTP request/response logging
LOGFIRE_ENABLE_REQUEST_LOGGING=True
```

### 3. Local Development

For local development, Logfire automatically uses console logging with readable formatting. No additional setup required.

### 4. Production Deployment

For production, you can optionally configure cloud logging:

1. Sign up at https://logfire.pydantic.dev/
2. Create a project
3. Get your authentication token
4. Set `LOGFIRE_TOKEN` in your environment variables

## Architecture

### Initialization

Logfire is initialized in `src/main.py` during application startup:

```python
from src.logging_config import setup_logfire

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logfire(app)  # Initializes Logfire with FastAPI and Pydantic instrumentation
    # ... rest of startup
```

### Correlation IDs

Every HTTP request automatically receives a correlation ID via `CorrelationIDMiddleware`. This ID:
- Is added to request headers (`X-Correlation-ID`)
- Is included in all logs for that request
- Allows tracing requests across services

### Service Instrumentation

All services include structured logging:

#### CopilotService
- Health check timing and availability
- API call success/failure with response times
- Fallback to OpenAI scenarios
- Error context and retry attempts

#### MessengerAgentService
- Message processing start/end with timing
- Confidence score calculations
- Escalation decisions and reasoning
- Response generation metrics

#### ScraperService
- Website scraping attempts with URLs
- Content chunking statistics
- HTTP error responses and timeouts
- Content hash calculations

#### FacebookService
- Message send attempts and delivery status
- API error responses and rate limiting
- Authentication token validation

#### Repository
- Database operation timing
- Query success/failure rates
- Bot configuration lookups
- Message history storage metrics

## Usage Patterns

### Basic Logging

```python
import logfire

# Info log with structured data
logfire.info(
    "Operation completed",
    operation="scrape_website",
    url="https://example.com",
    chunk_count=5,
    response_time_ms=1234.5
)

# Warning log
logfire.warn(
    "Fallback triggered",
    service="copilot",
    reason="timeout"
)

# Error log
logfire.error(
    "Operation failed",
    error=str(e),
    error_type=type(e).__name__,
    retry_count=3
)
```

### Context Managers

Use context managers to add correlation data:

```python
with logfire.context(correlation_id=correlation_id):
    # All logs in this block will include correlation_id
    logfire.info("Processing request")
```

### Timing Operations

Logfire automatically tracks timing when used with FastAPI instrumentation. For manual timing:

```python
import time

start_time = time.time()
# ... operation ...
elapsed = time.time() - start_time

logfire.info(
    "Operation completed",
    response_time_ms=elapsed * 1000
)
```

### PII Masking

Sensitive data is automatically masked using utilities in `src/logging_config.py`:

```python
from src.logging_config import mask_pii, redact_tokens

# Mask a value
masked = mask_pii("secret-token-12345")  # Returns "se*********45"

# Redact tokens from a dict
safe_data = redact_tokens({
    "access_token": "secret",
    "api_key": "key123"
})
```

## Testing

### Test Fixtures

Use the `logfire_capture` fixture to capture logs in tests:

```python
def test_service_logs_operation(logfire_capture):
    # ... perform operation ...
    
    # Verify logging occurred
    assert len(logfire_capture) > 0
    
    # Find specific log
    operation_logs = [
        log for log in logfire_capture
        if "operation" in str(log[1]).lower()
    ]
    assert len(operation_logs) > 0
    
    # Verify structured data
    log_type, args, kwargs = operation_logs[0]
    assert "response_time_ms" in kwargs
```

### Mocking Logfire

Use the `mock_logfire` fixture to disable logging in tests:

```python
def test_service_without_logging(mock_logfire):
    # Logfire calls are mocked, no actual logging occurs
    # ... perform operation ...
```

## Log Levels

Configure log levels via `LOG_LEVEL` environment variable:

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (default)
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical errors requiring immediate attention

## Environment-Specific Behavior

### Local Development
- Console formatting with timestamps
- Human-readable log messages
- Full request/response logging

### Production
- Structured JSON logging
- Automatic PII masking
- Cloud logging (if token provided)
- Optimized for log aggregation systems

## Integration with Sentry

Logfire and Sentry work together:
- Logfire provides structured logging and tracing
- Sentry provides error tracking and alerting
- Correlation IDs link Logfire logs to Sentry errors

## Best Practices

1. **Always include timing metrics** for operations:
   ```python
   logfire.info("Operation", response_time_ms=elapsed * 1000)
   ```

2. **Include context in error logs**:
   ```python
   logfire.error(
       "Operation failed",
       error=str(e),
       error_type=type(e).__name__,
       context={"user_id": user_id, "operation": "send_message"}
   )
   ```

3. **Use structured data, not string formatting**:
   ```python
   # ✅ Good
   logfire.info("User logged in", user_id=user_id, timestamp=now)
   
   # ❌ Bad
   logfire.info(f"User {user_id} logged in at {now}")
   ```

4. **Mask sensitive data**:
   ```python
   from src.logging_config import mask_pii
   logfire.info("API call", token=mask_pii(api_token))
   ```

5. **Include correlation IDs** for distributed tracing:
   ```python
   with logfire.context(correlation_id=request.state.correlation_id):
       logfire.info("Processing request")
   ```

## Troubleshooting

### Logs not appearing
- Check `LOG_LEVEL` is set appropriately
- Verify Logfire is initialized in `src/main.py`
- Check console output for local development

### Performance impact
- Logfire is designed to be non-blocking
- Use appropriate log levels in production
- Consider disabling request logging if volume is too high

### Cloud logging not working
- Verify `LOGFIRE_TOKEN` is set correctly
- Check network connectivity
- Review Logfire dashboard for errors

## Resources

- [Pydantic Logfire Documentation](https://logfire.pydantic.dev/)
- [FastAPI Integration](https://logfire.pydantic.dev/integrations/fastapi/)
- [Pydantic Integration](https://logfire.pydantic.dev/integrations/pydantic/)
