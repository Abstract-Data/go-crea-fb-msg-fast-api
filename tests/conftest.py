"""Shared pytest fixtures and configuration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime
from typing import Any
from fastapi.testclient import TestClient
import respx

from src.services.copilot_service import CopilotService
from src.models.agent_models import AgentContext, AgentResponse
from src.models.config_models import BotConfiguration
from src.main import app


@pytest.fixture
def respx_mock():
    """Respx mock fixture for HTTP mocking."""
    with respx.mock:
        yield respx


@pytest.fixture
def mock_copilot_service():
    """Mock CopilotService for testing."""
    copilot = AsyncMock(spec=CopilotService)
    copilot.base_url = "http://localhost:5909"
    copilot.enabled = True
    copilot.is_available = AsyncMock(return_value=True)
    copilot.chat = AsyncMock(return_value="Test response from Copilot")
    copilot.synthesize_reference = AsyncMock(
        return_value="# Test Reference Document\n\nThis is a test reference document."
    )
    copilot._fallback_to_openai = AsyncMock(return_value="Fallback response")
    return copilot


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
    
    # Chain: table().select().eq().execute()
    execute_mock.data = []
    eq_mock.execute.return_value = execute_mock
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
    """Mock httpx.AsyncClient for testing."""
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
    
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.post = AsyncMock(side_effect=mock_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    
    return mock_client


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
        "is_active": True
    }


@pytest.fixture
def sample_bot_configuration(sample_bot_config):
    """Sample BotConfiguration model instance."""
    return BotConfiguration(**sample_bot_config)


@pytest.fixture
def sample_reference_doc():
    """Sample reference document content for testing."""
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
def sample_agent_context(sample_reference_doc):
    """Sample AgentContext for testing."""
    return AgentContext(
        bot_config_id="bot-123",
        reference_doc=sample_reference_doc,
        tone="professional",
        recent_messages=["Hello", "How can I help?"]
    )


@pytest.fixture
def sample_agent_response():
    """Sample AgentResponse for testing."""
    return AgentResponse(
        message="This is a test response",
        confidence=0.85,
        requires_escalation=False,
        escalation_reason=None
    )


@pytest.fixture
def test_client():
    """FastAPI TestClient for E2E tests."""
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
        copilot_cli_host="http://localhost:5909",
        copilot_enabled=True,
        openai_api_key="test-openai-key",
        env="local"
    )
    
    monkeypatch.setattr("src.config.get_settings", lambda: settings)
    return settings
