"""Shared pytest fixtures and configuration.

This module centralizes all test fixtures to:
- Eliminate duplicate fixtures across test files
- Provide consistent test data structures
- Make tests more maintainable
- Enable easier fixture customization

Fixture Categories:
1. Mock Services: mock_agent_service, mock_messaging_service, mock_message_processor
2. Mock Models: mock_bot_config, mock_user_profile, mock_agent_response, mock_ref_doc
3. Security Mocks: mock_rate_limiter_*, mock_prompt_guard_*
4. Infrastructure: mock_supabase_client, mock_httpx_client, mock_settings, mock_logfire
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime

try:
    import respx
except ImportError:
    respx = None

try:
    import logfire
except ImportError:
    logfire = None

from src.models.agent_models import AgentContext, AgentResponse
from src.models.config_models import BotConfiguration
from src.models.user_models import FacebookUserInfo, UserProfileCreate

# Configure logfire for tests if available
if logfire is not None:
    # Set ignore_no_config to suppress warnings when logfire isn't fully configured
    # This allows tests to run without requiring full logfire setup
    os.environ.setdefault("LOGFIRE_IGNORE_NO_CONFIG", "1")

    # Try to configure logfire if token is available
    try:
        from src.config import get_settings

        settings = get_settings()
        if hasattr(settings, "logfire_token") and settings.logfire_token:
            logfire.configure(
                project_name="facebook-messenger-scrape-bot",
                environment="test",
                token=settings.logfire_token,
            )
    except Exception:
        # If configuration fails, ignore_no_config will suppress warnings
        pass


@pytest.fixture
def respx_mock():
    """Respx mock fixture for HTTP mocking."""
    if respx is None:
        pytest.skip("respx not available")
    with respx.mock:
        yield respx


@pytest.fixture
def mock_agent_service(mock_agent_response):
    """Mock MessengerAgentService for testing.

    Returns a fully configured mock agent service with:
    - respond() returning mock_agent_response
    - respond_with_fallback() returning a fallback response

    Uses the mock_agent_response fixture, which can be overridden in tests.
    """
    from src.services.agent_service import MessengerAgentService

    agent_service = AsyncMock(spec=MessengerAgentService)
    agent_service.respond = AsyncMock(return_value=mock_agent_response)
    agent_service.respond_with_fallback = AsyncMock(
        return_value=AgentResponse(
            message="Fallback response",
            confidence=0.8,
            requires_escalation=False,
        )
    )
    return agent_service


@pytest.fixture
def mock_agent_service_basic():
    """Basic mock agent service without fixture dependencies.

    Use this when you don't need the mock_agent_response fixture
    or want to configure the response yourself in the test.
    """
    from src.services.agent_service import MessengerAgentService

    agent_service = AsyncMock(spec=MessengerAgentService)
    agent_service.respond = AsyncMock(
        return_value=AgentResponse(
            message="Test response from agent",
            confidence=0.85,
            requires_escalation=False,
        )
    )
    agent_service.respond_with_fallback = AsyncMock(
        return_value=AgentResponse(
            message="Fallback response",
            confidence=0.8,
            requires_escalation=False,
        )
    )
    return agent_service


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    client = MagicMock()

    # Mock table chain
    table_mock = MagicMock()
    select_mock = MagicMock()
    eq_mock = MagicMock()
    insert_mock = MagicMock()
    update_mock = MagicMock()
    execute_mock = MagicMock()

    # Chain: table().select().eq().eq().execute() (handles multiple eq calls)
    execute_mock.data = []
    eq_mock2 = MagicMock()
    eq_mock2.execute.return_value = execute_mock
    eq_mock.execute.return_value = execute_mock
    eq_mock.eq.return_value = eq_mock2  # Support chained eq() calls
    select_mock.eq.return_value = eq_mock
    table_mock.select.return_value = select_mock

    # Chain: table().insert().execute()
    insert_execute_mock = MagicMock()
    insert_execute_mock.data = []
    insert_mock.execute.return_value = insert_execute_mock
    table_mock.insert.return_value = insert_mock

    # Chain: table().update().eq().execute()
    update_execute_mock = MagicMock()
    update_execute_mock.data = []
    update_mock.eq.return_value = MagicMock()
    update_mock.eq.return_value.execute.return_value = update_execute_mock
    table_mock.update.return_value = update_mock

    client.table.return_value = table_mock

    return client


@pytest.fixture
def mock_httpx_client(monkeypatch):
    """Mock httpx.AsyncClient for testing with proper cleanup simulation."""

    async def mock_get(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = Mock()
        return mock_response

    async def mock_post(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": "Test response"}
        mock_response.raise_for_status = Mock()
        return mock_response

    async def mock_close():
        """Simulate closing the HTTP client to clean up resources."""
        return None

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.post = AsyncMock(side_effect=mock_post)
    mock_client.close = AsyncMock(side_effect=mock_close)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)  # This closes properly

    return mock_client


# =============================================================================
# Messaging Service Mocks
# =============================================================================


@pytest.fixture
def mock_messaging_service():
    """Mock messaging service for testing MessageProcessor.

    Provides a fully configured mock with:
    - send_message() returning True (success)
    - get_user_info() returning None (no user info)

    To return user info, override get_user_info.return_value in your test.
    """
    service = MagicMock()
    service.send_message = AsyncMock(return_value=True)
    service.get_user_info = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_messaging_service_with_user(sample_facebook_user_info):
    """Mock messaging service that returns user info.

    Useful for testing user profile creation flows.
    """
    service = MagicMock()
    service.send_message = AsyncMock(return_value=True)
    service.get_user_info = AsyncMock(return_value=sample_facebook_user_info)
    return service


# =============================================================================
# Message Processor Mocks
# =============================================================================


@pytest.fixture
def mock_message_processor():
    """Mock MessageProcessor for webhook tests.

    Provides a mock with async process() method that can be configured
    to succeed, raise errors, or track calls.
    """
    processor = MagicMock()
    processor.process = AsyncMock()
    return processor


# =============================================================================
# Rate Limiter Mocks
# =============================================================================


@pytest.fixture
def mock_rate_limiter_passing():
    """Mock rate limiter that allows all requests.

    Use when testing message flow where rate limiting should pass.
    """
    limiter = MagicMock()
    limiter.check_rate_limit = MagicMock(return_value=True)
    limiter.get_remaining_requests = MagicMock(return_value=10)
    return limiter


@pytest.fixture
def mock_rate_limiter_blocking():
    """Mock rate limiter that blocks all requests.

    Use when testing rate limit exceeded scenarios.
    """
    limiter = MagicMock()
    limiter.check_rate_limit = MagicMock(return_value=False)
    limiter.get_remaining_requests = MagicMock(return_value=0)
    return limiter


# =============================================================================
# Prompt Guard Mocks
# =============================================================================


@pytest.fixture
def mock_prompt_guard_safe():
    """Mock prompt guard that allows all messages.

    Use when testing message flow where injection checks should pass.
    """
    guard = MagicMock()
    guard.check = MagicMock(
        return_value=MagicMock(
            is_suspicious=False,
            matched_pattern=None,
            risk_level="low",
        )
    )
    guard.is_blocked = MagicMock(return_value=False)
    return guard


@pytest.fixture
def mock_prompt_guard_high_risk():
    """Mock prompt guard that detects high-risk injection.

    Use when testing prompt injection blocking scenarios.
    """
    guard = MagicMock()
    guard.check = MagicMock(
        return_value=MagicMock(
            is_suspicious=True,
            matched_pattern="ignore_instructions",
            risk_level="high",
        )
    )
    guard.is_blocked = MagicMock(return_value=True)
    return guard


@pytest.fixture
def mock_prompt_guard_medium_risk():
    """Mock prompt guard that detects medium-risk pattern.

    Use when testing medium-risk scenarios (logged but not blocked).
    """
    guard = MagicMock()
    guard.check = MagicMock(
        return_value=MagicMock(
            is_suspicious=True,
            matched_pattern="new_instructions",
            risk_level="medium",
        )
    )
    guard.is_blocked = MagicMock(return_value=False)
    return guard


# =============================================================================
# Model Fixtures - Bot Configuration
# =============================================================================


@pytest.fixture
def sample_bot_config():
    """Sample bot configuration dict for testing."""
    return {
        "id": "bot-123",
        "page_id": "page-123",
        "website_url": "https://example.com",
        "reference_doc_id": "doc-123",
        "tone": "professional",
        "facebook_page_access_token": "token-123",
        "facebook_verify_token": "verify-123",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "is_active": True,
    }


@pytest.fixture
def sample_bot_configuration(sample_bot_config):
    """Sample BotConfiguration model instance."""
    return BotConfiguration(**sample_bot_config)


@pytest.fixture
def mock_bot_config():
    """Mock bot configuration as MagicMock for attribute access.

    Use this when you need a mock that can have its attributes
    accessed and modified easily, rather than a Pydantic model.

    This is useful for patching get_bot_configuration_by_page_id().
    """
    config = MagicMock()
    config.id = "bot-1"
    config.page_id = "page-1"
    config.website_url = "https://example.com"
    config.reference_doc_id = "doc-1"
    config.tone = "friendly"
    config.facebook_page_access_token = "token-123"
    config.facebook_verify_token = "verify-123"
    config.tenant_id = None
    config.is_active = True
    return config


@pytest.fixture
def sample_reference_doc():
    """Sample reference document content for testing (string content).

    Use this when you need just the reference document text content.
    """
    return """# Overview
This is a test organization.

## Services
- Service 1: Description of service 1
- Service 2: Description of service 2

## Contact
Email: info@example.com
Phone: 555-1234

## Policies
Our policy is to provide excellent service.
"""


@pytest.fixture
def mock_ref_doc():
    """Sample reference document as dict with all fields.

    Use this when you need the full reference document structure
    as returned by get_reference_document().
    """
    return {
        "id": "doc-1",
        "content": "# Reference\nTest content for the bot.",
        "source_url": "https://example.com",
        "content_hash": "abc123hash",
        "created_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Model Fixtures - User Profile
# =============================================================================


@pytest.fixture
def mock_user_profile():
    """Sample user profile dict for testing.

    Represents a user profile as returned from the database.
    """
    return {
        "id": "profile-1",
        "sender_id": "user-1",
        "page_id": "page-1",
        "first_name": "Jane",
        "last_name": "Doe",
        "profile_pic": "https://example.com/pic.jpg",
        "locale": "en_US",
        "timezone": -6,
        "location_title": "Austin, TX",
        "location_lat": 30.27,
        "location_long": -97.74,
        "location_address": "123 Main St, Austin, TX",
        "first_interaction_at": datetime.utcnow().isoformat(),
        "last_interaction_at": datetime.utcnow().isoformat(),
        "total_messages": 5,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_user_profile_create():
    """Sample UserProfileCreate model for testing profile creation."""
    return UserProfileCreate(
        sender_id="user-1",
        page_id="page-1",
        first_name="Jane",
        last_name="Doe",
        locale="en_US",
        timezone=-6,
    )


@pytest.fixture
def sample_facebook_user_info():
    """Sample FacebookUserInfo for testing Facebook API responses."""
    return FacebookUserInfo(
        id="user-1",
        first_name="Jane",
        last_name="Doe",
        profile_pic="https://example.com/pic.jpg",
        locale="en_US",
        timezone=-6,
    )


@pytest.fixture
def sample_agent_context(sample_reference_doc):
    """Sample AgentContext for testing."""
    return AgentContext(
        bot_config_id="bot-123",
        reference_doc_id="ref-doc-123",
        reference_doc=sample_reference_doc,
        tone="professional",
        recent_messages=["Hello", "How can I help?"],
    )


@pytest.fixture
def sample_agent_response():
    """Sample AgentResponse for testing.

    Standard response with high confidence, no escalation.
    """
    return AgentResponse(
        message="This is a test response",
        confidence=0.85,
        requires_escalation=False,
        escalation_reason=None,
    )


@pytest.fixture
def mock_agent_response():
    """Mock agent response for MessageProcessor tests.

    Provides a response suitable for message processing tests
    with clear, friendly message content.
    """
    return AgentResponse(
        message="Hello! How can I help you today?",
        confidence=0.92,
        requires_escalation=False,
        escalation_reason=None,
    )


@pytest.fixture
def sample_agent_response_low_confidence():
    """Sample AgentResponse with low confidence for escalation testing."""
    return AgentResponse(
        message="I'm not entirely sure about this, but...",
        confidence=0.3,
        requires_escalation=True,
        escalation_reason="Low confidence on complex query",
    )


@pytest.fixture
def sample_agent_response_escalation():
    """Sample AgentResponse that requires escalation."""
    return AgentResponse(
        message="I need to connect you with a human agent.",
        confidence=0.4,
        requires_escalation=True,
        escalation_reason="Out of scope query",
    )


@pytest.fixture
def test_client(mock_settings, mock_logfire):
    """FastAPI TestClient for E2E tests."""
    from fastapi.testclient import TestClient
    from src.main import app

    return TestClient(app)


@pytest.fixture
def mock_facebook_api(monkeypatch):
    """Mock Facebook Graph API responses."""

    async def mock_post(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        return mock_response

    return mock_post


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock application settings."""
    from src.config import Settings

    settings = Settings(
        facebook_page_access_token="test-page-token",
        facebook_verify_token="test-verify-token",
        facebook_app_secret="test-app-secret",
        supabase_url="https://test.supabase.co",
        supabase_service_key="test-service-key",
        pydantic_ai_gateway_api_key="paig_test_key",
        default_model="gateway/anthropic:claude-3-5-sonnet-latest",
        fallback_model="gateway/anthropic:claude-3-5-haiku-latest",
        openai_api_key="test-openai-key",
        env="local",
        logfire_token=None,
    )

    monkeypatch.setattr("src.config.get_settings", lambda: settings)
    # Patch where get_settings is used so request handlers see the mock
    monkeypatch.setattr("src.main.get_settings", lambda: settings)
    # Patch scraper and facebook_service modules that now use configurable timeouts
    monkeypatch.setattr("src.services.scraper.get_settings", lambda: settings)
    monkeypatch.setattr("src.services.facebook_service.get_settings", lambda: settings)
    return settings


@pytest.fixture
def logfire_capture():
    """
    Capture Logfire logs for testing.

    This fixture patches Logfire to capture log calls for assertion.
    """
    if logfire is None:
        pytest.skip("logfire not available")

    captured_logs = []

    original_info = logfire.info
    original_warn = logfire.warn
    original_error = logfire.error

    def capture_info(*args, **kwargs):
        captured_logs.append(("info", args, kwargs))
        return original_info(*args, **kwargs)

    def capture_warn(*args, **kwargs):
        captured_logs.append(("warn", args, kwargs))
        return original_warn(*args, **kwargs)

    def capture_error(*args, **kwargs):
        captured_logs.append(("error", args, kwargs))
        return original_error(*args, **kwargs)

    with (
        patch("logfire.info", side_effect=capture_info),
        patch("logfire.warn", side_effect=capture_warn),
        patch("logfire.error", side_effect=capture_error),
    ):
        yield captured_logs


@pytest.fixture
def mock_logfire(monkeypatch):
    """
    Mock Logfire for testing without actual logging.

    Useful for tests that don't need to verify logging behavior.
    Auto-applied to all tests to prevent logfire.context errors.
    """
    from contextlib import contextmanager
    import sys

    @contextmanager
    def mock_span(*args, **kwargs):
        yield {}

    mock_logfire_module = MagicMock()
    mock_logfire_module.info = Mock()
    mock_logfire_module.warn = Mock()
    mock_logfire_module.error = Mock()
    mock_logfire_module.span = mock_span
    mock_logfire_module.context = mock_span  # For backwards compatibility if used
    mock_logfire_module.configure = Mock()
    mock_logfire_module.instrument_fastapi = Mock()
    mock_logfire_module.instrument_pydantic = Mock()
    mock_logfire_module.instrument_pydantic_ai = Mock()

    # Patch logfire in sys.modules to affect all imports (only patch attributes that exist)
    if "logfire" in sys.modules:
        original_logfire = sys.modules["logfire"]
        for attr in [
            "info",
            "warn",
            "error",
            "span",
            "configure",
            "instrument_fastapi",
            "instrument_pydantic",
            "instrument_pydantic_ai",
        ]:
            if hasattr(original_logfire, attr):
                monkeypatch.setattr(
                    original_logfire, attr, getattr(mock_logfire_module, attr)
                )
        if hasattr(original_logfire, "context"):
            monkeypatch.setattr(
                original_logfire, "context", mock_logfire_module.context
            )

    # Also patch module-level imports in our code (only modules that use logfire)
    monkeypatch.setattr("src.services.scraper.logfire", mock_logfire_module)
    monkeypatch.setattr("src.services.facebook_service.logfire", mock_logfire_module)
    monkeypatch.setattr("src.db.repository.logfire", mock_logfire_module)
    monkeypatch.setattr("src.middleware.correlation_id.logfire", mock_logfire_module)
    monkeypatch.setattr("src.logging_config.logfire", mock_logfire_module)

    return mock_logfire_module
