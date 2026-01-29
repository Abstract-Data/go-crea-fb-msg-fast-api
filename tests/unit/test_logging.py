"""Tests for structured logging with Logfire."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.copilot_service import CopilotService
from src.services.agent_service import MessengerAgentService
from src.services.scraper import scrape_website
from src.services.facebook_service import send_message
from src.db.repository import (
    create_reference_document,
    get_bot_configuration_by_page_id,
    save_message_history,
)
from src.models.agent_models import AgentContext


@pytest.mark.asyncio
async def test_copilot_service_logs_health_check(logfire_capture, respx_mock):
    """Test that CopilotService logs health check attempts."""
    respx_mock.get("http://localhost:5909/health").mock(return_value=200)
    
    copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
    await copilot.is_available()
    
    # Verify logging occurred
    assert len(logfire_capture) > 0
    
    # Find health check log
    health_logs = [
        log for log in logfire_capture
        if log[0] in ("info", "warn") and "health check" in str(log[1]).lower()
    ]
    assert len(health_logs) > 0
    
    # Verify structured data
    log_type, args, kwargs = health_logs[0]
    assert "available" in kwargs or "status_code" in kwargs
    assert "response_time_ms" in kwargs


@pytest.mark.asyncio
async def test_copilot_service_logs_chat_attempts(logfire_capture, respx_mock):
    """Test that CopilotService logs chat attempts with timing."""
    respx_mock.get("http://localhost:5909/health").mock(return_value=200)
    respx_mock.post("http://localhost:5909/chat").mock(
        return_value={"content": "Test response"}
    )
    
    copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
    await copilot.chat("System prompt", [{"role": "user", "content": "Hello"}])
    
    # Find chat logs
    chat_logs = [
        log for log in logfire_capture
        if "chat" in str(log[1]).lower() or "chat" in str(kwargs).lower()
        for kwargs in [log[2]]
    ]
    assert len(chat_logs) > 0
    
    # Verify structured data includes timing
    log_type, args, kwargs = chat_logs[0]
    assert "response_time_ms" in kwargs
    assert "message_count" in kwargs or "success" in kwargs


@pytest.mark.asyncio
async def test_agent_service_logs_processing(logfire_capture, mock_copilot_service):
    """Test that MessengerAgentService logs message processing."""
    agent = MessengerAgentService(copilot=mock_copilot_service)
    context = AgentContext(
        bot_config_id="bot-123",
        reference_doc="Test reference",
        tone="professional",
        recent_messages=[]
    )
    
    await agent.respond(context, "Test message")
    
    # Verify processing logs
    processing_logs = [
        log for log in logfire_capture
        if "processing" in str(log[1]).lower() or "processing" in str(log[2]).lower()
    ]
    assert len(processing_logs) > 0
    
    # Verify response generation logs
    response_logs = [
        log for log in logfire_capture
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
        return_value="<html><body>Test content with many words " * 100 + "</body></html>"
    )
    
    chunks = await scrape_website("https://example.com")
    
    # Verify scraping logs
    scrape_logs = [
        log for log in logfire_capture
        if "scrape" in str(log[1]).lower() or "scrape" in str(log[2]).lower()
    ]
    assert len(scrape_logs) > 0
    
    # Verify completion log has metrics
    completion_logs = [
        log for log in scrape_logs
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
        return_value={"message_id": "msg-123"}
    )
    
    await send_message("token", "recipient-123", "Test message")
    
    # Verify send logs
    send_logs = [
        log for log in logfire_capture
        if "message" in str(log[1]).lower() or "message" in str(log[2]).lower()
    ]
    assert len(send_logs) > 0
    
    # Verify success log
    success_logs = [
        log for log in send_logs
        if "success" in str(log[1]).lower() or "success" in str(log[2]).lower()
    ]
    assert len(success_logs) > 0
    
    log_type, args, kwargs = success_logs[0]
    assert "status_code" in kwargs
    assert "response_time_ms" in kwargs


def test_repository_logs_document_creation(logfire_capture, mock_supabase_client, monkeypatch):
    """Test that repository logs document creation."""
    from src.db import client
    
    monkeypatch.setattr(client, "get_supabase_client", lambda: mock_supabase_client)
    
    # Setup mock response
    mock_supabase_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "doc-123"}
    ]
    
    create_reference_document("Content", "https://example.com", "hash123")
    
    # Verify creation logs
    creation_logs = [
        log for log in logfire_capture
        if "reference document" in str(log[1]).lower() or "reference document" in str(log[2]).lower()
    ]
    assert len(creation_logs) >= 2  # Start and completion
    
    # Verify completion log
    completion_logs = [
        log for log in creation_logs
        if "created" in str(log[1]).lower() or "created" in str(log[2]).lower()
    ]
    assert len(completion_logs) > 0
    
    log_type, args, kwargs = completion_logs[0]
    assert "document_id" in kwargs
    assert "response_time_ms" in kwargs


def test_repository_logs_bot_config_lookup(logfire_capture, mock_supabase_client, monkeypatch):
    """Test that repository logs bot configuration lookups."""
    from src.db import client
    
    monkeypatch.setattr(client, "get_supabase_client", lambda: mock_supabase_client)
    
    # Setup mock response
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "bot-123", "page_id": "page-123"}
    ]
    
    get_bot_configuration_by_page_id("page-123")
    
    # Verify lookup logs
    lookup_logs = [
        log for log in logfire_capture
        if "bot configuration" in str(log[1]).lower() or "bot configuration" in str(log[2]).lower()
    ]
    assert len(lookup_logs) > 0
    
    log_type, args, kwargs = lookup_logs[0]
    assert "page_id" in kwargs


def test_repository_logs_message_history_save(logfire_capture, mock_supabase_client, monkeypatch):
    """Test that repository logs message history saves."""
    from src.db import client
    
    monkeypatch.setattr(client, "get_supabase_client", lambda: mock_supabase_client)
    
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
        requires_escalation=False
    )
    
    # Verify save logs
    save_logs = [
        log for log in logfire_capture
        if "message history" in str(log[1]).lower() or "message history" in str(log[2]).lower()
    ]
    assert len(save_logs) >= 2  # Start and completion
    
    # Verify completion log
    completion_logs = [
        log for log in save_logs
        if "saved" in str(log[1]).lower() or "saved" in str(log[2]).lower()
    ]
    assert len(completion_logs) > 0
    
    log_type, args, kwargs = completion_logs[0]
    assert "bot_id" in kwargs
    assert "confidence" in kwargs
    assert "response_time_ms" in kwargs
