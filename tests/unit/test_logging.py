"""Tests for structured logging with Logfire."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import httpx

from src.services.agent_service import MessengerAgentService
from src.services.scraper import scrape_website
from src.services.facebook_service import send_message
from src.db.repository import (
    create_reference_document,
    get_bot_configuration_by_page_id,
    save_message_history,
)
from src.models.agent_models import AgentContext


@pytest.mark.skip(reason="CopilotService removed - migrated to PydanticAI Gateway")
@pytest.mark.asyncio
async def test_copilot_service_logs_health_check(logfire_capture, respx_mock):
    """Test that CopilotService logs health check attempts."""
    pass


@pytest.mark.skip(reason="CopilotService removed - migrated to PydanticAI Gateway")
@pytest.mark.asyncio
async def test_copilot_service_logs_chat_attempts(logfire_capture, respx_mock):
    """Test that CopilotService logs chat attempts with timing."""
    pass


@pytest.mark.asyncio
@patch("src.services.agent_service.get_settings")
@pytest.mark.skip(
    reason="MessengerAgentService uses logging.getLogger, not logfire; logfire_capture does not capture stdlib logs"
)
async def test_agent_service_logs_processing(
    mock_get_settings, logfire_capture, monkeypatch
):
    """Test that MessengerAgentService logs message processing."""
    from src.config import Settings

    # Set environment variable for PydanticAI Gateway
    monkeypatch.setenv("PYDANTIC_AI_GATEWAY_API_KEY", "paig_test_key")

    # Mock settings for agent initialization
    mock_settings = Settings(
        facebook_page_access_token="test-token",
        facebook_verify_token="test-verify",
        supabase_url="https://test.supabase.co",
        supabase_service_key="test-key",
        pydantic_ai_gateway_api_key="paig_test_key",
    )
    mock_get_settings.return_value = mock_settings

    agent = MessengerAgentService()
    context = AgentContext(
        bot_config_id="bot-123",
        reference_doc_id="ref-doc-123",
        reference_doc="Test reference",
        tone="professional",
        recent_messages=[],
    )

    await agent.respond(context, "Test message")

    # Verify processing logs
    processing_logs = [
        log
        for log in logfire_capture
        if "processing" in str(log[1]).lower() or "processing" in str(log[2]).lower()
    ]
    assert len(processing_logs) > 0

    # Verify response generation logs
    response_logs = [
        log
        for log in logfire_capture
        if "response" in str(log[1]).lower() or "response" in str(log[2]).lower()
    ]
    assert len(response_logs) > 0

    # Verify structured data
    log_type, args, kwargs = response_logs[0]
    assert "confidence" in kwargs
    assert "response_time_ms" in kwargs


@pytest.mark.asyncio
async def test_scraper_logs_scraping_metrics(logfire_capture, respx_mock):
    """Test that scraper logs scraping metrics."""
    respx_mock.get("https://example.com").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Test content with many words " * 100 + "</body></html>",
        )
    )

    result = await scrape_website("https://example.com")
    _ = result.chunks  # ensure we have chunks for log verification

    # Verify scraping logs
    scrape_logs = [
        log
        for log in logfire_capture
        if "scrape" in str(log[1]).lower() or "scrape" in str(log[2]).lower()
    ]
    assert len(scrape_logs) > 0

    # Verify completion log has metrics
    completion_logs = [
        log
        for log in scrape_logs
        if "completed" in str(log[1]).lower() or "completed" in str(log[2]).lower()
    ]
    assert len(completion_logs) > 0

    log_type, args, kwargs = completion_logs[0]
    assert "chunk_count" in kwargs
    assert "total_time_ms" in kwargs
    assert "content_hash" in kwargs


@pytest.mark.asyncio
async def test_facebook_service_logs_message_sends(logfire_capture, respx_mock):
    """Test that FacebookService logs message send attempts."""
    respx_mock.post("https://graph.facebook.com/v18.0/me/messages").mock(
        return_value=httpx.Response(200, json={"message_id": "msg-123"})
    )

    await send_message("token", "recipient-123", "Test message")

    # Verify send logs
    send_logs = [
        log
        for log in logfire_capture
        if "message" in str(log[1]).lower() or "message" in str(log[2]).lower()
    ]
    assert len(send_logs) > 0

    # Verify success log
    success_logs = [
        log
        for log in send_logs
        if "success" in str(log[1]).lower() or "success" in str(log[2]).lower()
    ]
    assert len(success_logs) > 0

    log_type, args, kwargs = success_logs[0]
    assert "status_code" in kwargs
    assert "response_time_ms" in kwargs


def test_repository_logs_document_creation(
    logfire_capture, mock_supabase_client, monkeypatch
):
    """Test that repository logs document creation."""
    from src.db import repository

    monkeypatch.setattr(repository, "get_supabase_client", lambda: mock_supabase_client)

    # Setup mock response
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "doc-123"}
    ]

    create_reference_document("Content", "https://example.com", "hash123")

    # Verify creation logs
    creation_logs = [
        log
        for log in logfire_capture
        if "reference document" in str(log[1]).lower()
        or "reference document" in str(log[2]).lower()
    ]
    assert len(creation_logs) >= 2  # Start and completion

    # Verify completion log
    completion_logs = [
        log
        for log in creation_logs
        if "created" in str(log[1]).lower() or "created" in str(log[2]).lower()
    ]
    assert len(completion_logs) > 0

    log_type, args, kwargs = completion_logs[0]
    assert "document_id" in kwargs
    assert "response_time_ms" in kwargs


def test_repository_logs_bot_config_lookup(
    logfire_capture, mock_supabase_client, monkeypatch
):
    """Test that repository logs bot configuration lookups."""
    from src.db import repository

    monkeypatch.setattr(repository, "get_supabase_client", lambda: mock_supabase_client)

    # Setup mock response with all required BotConfiguration fields
    # Need to set on the second eq() call chain: select().eq().eq().execute()
    eq2_mock = (
        mock_supabase_client.table.return_value.select.return_value.eq.return_value
    )
    eq2_mock.eq.return_value.execute.return_value.data = [
        {
            "id": "bot-123",
            "page_id": "page-123",
            "website_url": "https://example.com",
            "reference_doc_id": "doc-123",
            "tone": "professional",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "is_active": True,
        }
    ]

    get_bot_configuration_by_page_id("page-123")

    # Verify lookup logs
    lookup_logs = [
        log
        for log in logfire_capture
        if "bot configuration" in str(log[1]).lower()
        or "bot configuration" in str(log[2]).lower()
    ]
    assert len(lookup_logs) > 0

    log_type, args, kwargs = lookup_logs[0]
    assert "page_id" in kwargs


def test_repository_logs_message_history_save(
    logfire_capture, mock_supabase_client, monkeypatch
):
    """Test that repository logs message history saves."""
    from src.db import repository

    monkeypatch.setattr(repository, "get_supabase_client", lambda: mock_supabase_client)

    # Setup mock response
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "msg-123"}
    ]

    save_message_history(
        bot_id="bot-123",
        sender_id="sender-123",
        message_text="Hello",
        response_text="Hi there",
        confidence=0.85,
        requires_escalation=False,
    )

    # Verify save logs
    save_logs = [
        log
        for log in logfire_capture
        if "message history" in str(log[1]).lower()
        or "message history" in str(log[2]).lower()
    ]
    assert len(save_logs) >= 2  # Start and completion

    # Verify completion log
    completion_logs = [
        log
        for log in save_logs
        if "saved" in str(log[1]).lower() or "saved" in str(log[2]).lower()
    ]
    assert len(completion_logs) > 0

    log_type, args, kwargs = completion_logs[0]
    assert "bot_id" in kwargs
    assert "message_id" in kwargs
    assert "response_time_ms" in kwargs
