"""Tests for repository functions."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid

from src.db.repository import (
    create_reference_document,
    link_reference_document_to_bot,
    create_bot_configuration,
    get_bot_configuration_by_page_id,
    get_reference_document,
    get_reference_document_by_source_url,
    save_message_history
)
from src.models.config_models import BotConfiguration


class TestCreateReferenceDocument:
    """Test create_reference_document() function."""
    
    @patch('src.db.repository.get_supabase_client')
    def test_create_reference_document_valid_inputs(self, mock_get_client):
        """Test create_reference_document() with valid inputs."""
        # Mock Supabase client
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "doc-123", "content": "test", "source_url": "https://example.com"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        doc_id = create_reference_document(
            content="# Test Document",
            source_url="https://example.com",
            content_hash="abc123"
        )
        
        assert doc_id == "doc-123"
        
        # Verify insert was called correctly
        mock_client.table.assert_called_with("reference_documents")
        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["content"] == "# Test Document"
        assert insert_call["source_url"] == "https://example.com"
        assert insert_call["content_hash"] == "abc123"
    
    @patch('src.db.repository.get_supabase_client')
    def test_create_reference_document_failure(self, mock_get_client):
        """Test error handling when document creation fails."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []  # Empty data indicates failure
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        with pytest.raises(ValueError, match="Failed to create reference document"):
            create_reference_document(
                content="test",
                source_url="https://example.com",
                content_hash="hash"
            )


class TestLinkReferenceDocumentToBot:
    """Test link_reference_document_to_bot() function."""
    
    @patch('src.db.repository.get_supabase_client')
    def test_link_reference_document_to_bot(self, mock_get_client):
        """Test linking reference document to bot."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        link_reference_document_to_bot("doc-123", "bot-456")
        
        # Verify update was called
        mock_client.table.assert_called_with("reference_documents")
        table = mock_client.table.return_value
        table.update.assert_called_once_with({"bot_id": "bot-456"})
        table.update.return_value.eq.assert_called_once_with("id", "doc-123")
        table.update.return_value.eq.return_value.execute.assert_called_once()


class TestCreateBotConfiguration:
    """Test create_bot_configuration() function."""
    
    @patch('src.db.repository.link_reference_document_to_bot')
    @patch('src.db.repository.get_supabase_client')
    def test_create_bot_configuration_valid_inputs(self, mock_get_client, mock_link):
        """Test create_bot_configuration() with valid inputs."""
        mock_client = MagicMock()
        now = datetime.utcnow()
        
        # The mock will return data based on what's inserted
        def mock_insert_execute():
            result = MagicMock()
            # Get the inserted data from the mock call
            insert_data = mock_client.table.return_value.insert.call_args[0][0]
            result.data = [{
                **insert_data,
            }]
            return result
        
        mock_client.table.return_value.insert.return_value.execute = mock_insert_execute
        mock_get_client.return_value = mock_client
        
        config = create_bot_configuration(
            page_id="page-123",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="professional",
            facebook_page_access_token="token",
            facebook_verify_token="verify"
        )
        
        assert isinstance(config, BotConfiguration)
        assert config.page_id == "page-123"
        assert config.website_url == "https://example.com"
        assert config.tone == "professional"
        
        # Verify link was called with correct doc_id
        mock_link.assert_called_once()
        call_args = mock_link.call_args[0]
        assert call_args[0] == "doc-123"  # First arg is doc_id
    
    @patch('src.db.repository.get_supabase_client')
    def test_create_bot_configuration_failure(self, mock_get_client):
        """Test error handling when bot configuration creation fails."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        with pytest.raises(ValueError, match="Failed to create bot configuration"):
            create_bot_configuration(
                page_id="page-123",
                website_url="https://example.com",
                reference_doc_id="doc-123",
                tone="professional",
                facebook_page_access_token="token",
                facebook_verify_token="verify"
            )


class TestGetBotConfigurationByPageId:
    """Test get_bot_configuration_by_page_id() function."""
    
    @patch('src.db.repository.get_supabase_client')
    def test_get_bot_configuration_by_page_id_found(self, mock_get_client):
        """Test get_bot_configuration_by_page_id() when configuration is found."""
        mock_client = MagicMock()
        now = datetime.utcnow()
        
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "bot-123",
            "page_id": "page-123",
            "website_url": "https://example.com",
            "reference_doc_id": "doc-123",
            "tone": "professional",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "is_active": True
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        config = get_bot_configuration_by_page_id("page-123")
        
        assert isinstance(config, BotConfiguration)
        assert config.page_id == "page-123"
        
        # Verify table was queried
        mock_client.table.assert_called_with("bot_configurations")
    
    @patch('src.db.repository.get_supabase_client')
    def test_get_bot_configuration_by_page_id_not_found(self, mock_get_client):
        """Test get_bot_configuration_by_page_id() when configuration is not found."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        config = get_bot_configuration_by_page_id("page-999")
        
        assert config is None


class TestGetReferenceDocument:
    """Test get_reference_document() function."""
    
    @patch('src.db.repository.get_supabase_client')
    def test_get_reference_document_found(self, mock_get_client):
        """Test get_reference_document() when document is found."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "doc-123",
            "content": "# Test Document",
            "source_url": "https://example.com",
            "content_hash": "abc123"
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        doc = get_reference_document("doc-123")
        
        assert doc is not None
        assert doc["id"] == "doc-123"
        assert doc["content"] == "# Test Document"
        
        # Verify query
        table = mock_client.table.return_value
        table.select.assert_called_once_with("*")
        table.select.return_value.eq.assert_called_once_with("id", "doc-123")
    
    @patch('src.db.repository.get_supabase_client')
    def test_get_reference_document_not_found(self, mock_get_client):
        """Test get_reference_document() when document is not found."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        doc = get_reference_document("doc-999")
        
        assert doc is None


class TestGetReferenceDocumentBySourceUrl:
    """Test get_reference_document_by_source_url() function."""

    @patch('src.db.repository.get_supabase_client')
    def test_get_reference_document_by_source_url_found(self, mock_get_client):
        """Test get_reference_document_by_source_url() when document is found."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "doc-456",
            "content": "# Existing Doc",
            "source_url": "https://example.com",
            "content_hash": "hash456"
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client

        doc = get_reference_document_by_source_url("https://example.com")

        assert doc is not None
        assert doc["id"] == "doc-456"
        assert doc["source_url"] == "https://example.com"
        mock_client.table.return_value.select.assert_called_once_with("*")
        mock_client.table.return_value.select.return_value.eq.assert_called_once_with("source_url", "https://example.com")

    @patch('src.db.repository.get_supabase_client')
    def test_get_reference_document_by_source_url_not_found(self, mock_get_client):
        """Test get_reference_document_by_source_url() when no document exists."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client

        doc = get_reference_document_by_source_url("https://unknown.com")

        assert doc is None

    @patch('src.db.repository.get_supabase_client')
    def test_get_reference_document_by_source_url_empty_url_returns_none(self, mock_get_client):
        """Test get_reference_document_by_source_url() with empty URL returns None without querying."""
        doc = get_reference_document_by_source_url("")
        assert doc is None
        doc = get_reference_document_by_source_url("   ")
        assert doc is None


class TestSaveMessageHistory:
    """Test save_message_history() function."""
    
    @patch('src.db.repository.get_supabase_client')
    def test_save_message_history(self, mock_get_client):
        """Test save_message_history() with all fields."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        save_message_history(
            bot_id="bot-123",
            sender_id="user-456",
            message_text="Hello",
            response_text="Hi there",
            confidence=0.85,
            requires_escalation=False
        )
        
        # Verify insert was called
        mock_client.table.assert_called_with("message_history")
        table = mock_client.table.return_value
        insert_call = table.insert.call_args[0][0]
        
        assert insert_call["bot_id"] == "bot-123"
        assert insert_call["sender_id"] == "user-456"
        assert insert_call["message_text"] == "Hello"
        assert insert_call["response_text"] == "Hi there"
        assert insert_call["confidence"] == 0.85
        assert insert_call["requires_escalation"] is False
        assert "created_at" in insert_call
    
    @patch('src.db.repository.get_supabase_client')
    def test_save_message_history_with_escalation(self, mock_get_client):
        """Test save_message_history() with escalation flag."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        save_message_history(
            bot_id="bot-123",
            sender_id="user-456",
            message_text="Question",
            response_text="I don't know",
            confidence=0.3,
            requires_escalation=True
        )
        
        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["requires_escalation"] is True
        assert insert_call["confidence"] == 0.3
