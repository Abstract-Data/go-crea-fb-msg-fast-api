"""Integration tests for repository with database operations."""

from unittest.mock import patch, MagicMock
from datetime import datetime

from src.db.repository import (
    create_bot_configuration,
    get_bot_configuration_by_page_id,
    create_reference_document,
    save_message_history,
)
from src.models.config_models import BotConfiguration


class TestRepositoryDatabaseIntegration:
    """Test repository operations with mocked Supabase."""

    @patch("src.db.repository.get_supabase_client")
    def test_bot_configuration_lifecycle(self, mock_get_client):
        """Test bot configuration lifecycle (create, read)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock create
        bot_id = "bot-123"
        now = datetime.utcnow()
        mock_result_create = MagicMock()
        mock_result_create.data = [
            {
                "id": bot_id,
                "page_id": "page-123",
                "website_url": "https://example.com",
                "reference_doc_id": "doc-123",
                "tone": "professional",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "is_active": True,
            }
        ]

        table_mock = MagicMock()
        table_mock.insert.return_value.execute.return_value = mock_result_create
        table_mock.update.return_value.eq.return_value.execute.return_value = (
            MagicMock()
        )
        table_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result_create
        mock_client.table.return_value = table_mock

        # Create bot configuration
        config = create_bot_configuration(
            page_id="page-123",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="professional",
            facebook_page_access_token="token",
            facebook_verify_token="verify",
        )

        assert isinstance(config, BotConfiguration)
        assert config.page_id == "page-123"

        # Get bot configuration
        retrieved_config = get_bot_configuration_by_page_id("page-123")

        assert retrieved_config is not None
        assert retrieved_config.page_id == "page-123"

    @patch("src.db.repository.get_supabase_client")
    def test_reference_document_creation(self, mock_get_client):
        """Test reference document creation."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [
            {"id": "doc-123", "content": "test", "source_url": "https://example.com"}
        ]

        table_mock = MagicMock()
        table_mock.insert.return_value.execute.return_value = mock_result
        mock_client.table.return_value = table_mock

        doc_id = create_reference_document(
            content="# Test Document",
            source_url="https://example.com",
            content_hash="hash123",
        )

        assert doc_id == "doc-123"

        # Verify insert was called with correct data
        insert_call = table_mock.insert.call_args[0][0]
        assert insert_call["content"] == "# Test Document"
        assert insert_call["source_url"] == "https://example.com"
        assert insert_call["content_hash"] == "hash123"

    @patch("src.db.repository.get_supabase_client")
    def test_message_history_storage(self, mock_get_client):
        """Test message history storage."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        table_mock = MagicMock()
        mock_client.table.return_value = table_mock

        save_message_history(
            bot_id="bot-123",
            sender_id="user-456",
            message_text="Hello",
            response_text="Hi there",
            confidence=0.85,
            requires_escalation=False,
        )

        # Verify insert was called
        table_mock.insert.assert_called_once()
        insert_call = table_mock.insert.call_args[0][0]

        assert insert_call["bot_id"] == "bot-123"
        assert insert_call["sender_id"] == "user-456"
        assert insert_call["message_text"] == "Hello"
        assert insert_call["response_text"] == "Hi there"
        assert insert_call["confidence"] == 0.85
        assert insert_call["requires_escalation"] is False
        assert "created_at" in insert_call

    @patch("src.db.repository.get_supabase_client")
    def test_message_history_with_escalation(self, mock_get_client):
        """Test message history storage with escalation."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        table_mock = MagicMock()
        mock_client.table.return_value = table_mock

        save_message_history(
            bot_id="bot-123",
            sender_id="user-456",
            message_text="Complex question",
            response_text="I don't know",
            confidence=0.3,
            requires_escalation=True,
        )

        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["requires_escalation"] is True
        assert insert_call["confidence"] == 0.3
