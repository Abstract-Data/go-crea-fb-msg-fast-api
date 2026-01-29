"""Tests for repository functions."""

import time

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.db.repository import (
    BotConfigCache,
    create_reference_document,
    link_reference_document_to_bot,
    create_bot_configuration,
    get_bot_config_cache,
    get_bot_configuration_by_page_id,
    get_reference_document,
    get_reference_document_by_source_url,
    get_user_profile,
    create_user_profile,
    reset_bot_config_cache,
    update_user_profile,
    upsert_user_profile,
    save_message_history,
    create_test_session,
    save_test_message,
)
from src.models.config_models import BotConfiguration
from src.models.user_models import UserProfileCreate, UserProfileUpdate


class TestCreateReferenceDocument:
    """Test create_reference_document() function."""

    @patch("src.db.repository.get_supabase_client")
    def test_create_reference_document_valid_inputs(self, mock_get_client):
        """Test create_reference_document() with valid inputs."""
        # Mock Supabase client
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {"id": "doc-123", "content": "test", "source_url": "https://example.com"}
        ]
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )
        mock_get_client.return_value = mock_client

        doc_id = create_reference_document(
            content="# Test Document",
            source_url="https://example.com",
            content_hash="abc123",
        )

        assert doc_id == "doc-123"

        # Verify insert was called correctly
        mock_client.table.assert_called_with("reference_documents")
        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["content"] == "# Test Document"
        assert insert_call["source_url"] == "https://example.com"
        assert insert_call["content_hash"] == "abc123"

    @patch("src.db.repository.get_supabase_client")
    def test_create_reference_document_failure(self, mock_get_client):
        """Test error handling when document creation fails."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []  # Empty data indicates failure
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ValueError, match="Failed to create reference document"):
            create_reference_document(
                content="test", source_url="https://example.com", content_hash="hash"
            )


class TestLinkReferenceDocumentToBot:
    """Test link_reference_document_to_bot() function."""

    @patch("src.db.repository.get_supabase_client")
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

    @patch("src.db.repository.link_reference_document_to_bot")
    @patch("src.db.repository.get_supabase_client")
    def test_create_bot_configuration_valid_inputs(self, mock_get_client, mock_link):
        """Test create_bot_configuration() with valid inputs."""
        mock_client = MagicMock()

        # The mock will return data based on what's inserted
        def mock_insert_execute():
            result = MagicMock()
            # Get the inserted data from the mock call
            insert_data = mock_client.table.return_value.insert.call_args[0][0]
            result.data = [
                {
                    **insert_data,
                }
            ]
            return result

        mock_client.table.return_value.insert.return_value.execute = mock_insert_execute
        mock_get_client.return_value = mock_client

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
        assert config.website_url == "https://example.com"
        assert config.tone == "professional"

        # Verify link was called with correct doc_id
        mock_link.assert_called_once()
        call_args = mock_link.call_args[0]
        assert call_args[0] == "doc-123"  # First arg is doc_id

    @patch("src.db.repository.get_supabase_client")
    def test_create_bot_configuration_failure(self, mock_get_client):
        """Test error handling when bot configuration creation fails."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ValueError, match="Failed to create bot configuration"):
            create_bot_configuration(
                page_id="page-123",
                website_url="https://example.com",
                reference_doc_id="doc-123",
                tone="professional",
                facebook_page_access_token="token",
                facebook_verify_token="verify",
            )


class TestGetBotConfigurationByPageId:
    """Test get_bot_configuration_by_page_id() function."""

    @patch("src.db.repository.get_supabase_client")
    def test_get_bot_configuration_by_page_id_found(self, mock_get_client):
        """Test get_bot_configuration_by_page_id() when configuration is found."""
        mock_client = MagicMock()
        now = datetime.utcnow()

        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "bot-123",
                "page_id": "page-123",
                "website_url": "https://example.com",
                "reference_doc_id": "doc-123",
                "tone": "professional",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "is_active": True,
            }
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client

        config = get_bot_configuration_by_page_id("page-123")

        assert isinstance(config, BotConfiguration)
        assert config.page_id == "page-123"

        # Verify table was queried
        mock_client.table.assert_called_with("bot_configurations")

    @patch("src.db.repository.get_supabase_client")
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

    @patch("src.db.repository.get_supabase_client")
    def test_get_reference_document_found(self, mock_get_client):
        """Test get_reference_document() when document is found."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "doc-123",
                "content": "# Test Document",
                "source_url": "https://example.com",
                "content_hash": "abc123",
            }
        ]
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

    @patch("src.db.repository.get_supabase_client")
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

    @patch("src.db.repository.get_supabase_client")
    def test_get_reference_document_by_source_url_found(self, mock_get_client):
        """Test get_reference_document_by_source_url() when document is found."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "doc-456",
                "content": "# Existing Doc",
                "source_url": "https://example.com",
                "content_hash": "hash456",
            }
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client

        doc = get_reference_document_by_source_url("https://example.com")

        assert doc is not None
        assert doc["id"] == "doc-456"
        assert doc["source_url"] == "https://example.com"
        mock_client.table.return_value.select.assert_called_once_with("*")
        mock_client.table.return_value.select.return_value.eq.assert_called_once_with(
            "source_url", "https://example.com"
        )

    @patch("src.db.repository.get_supabase_client")
    def test_get_reference_document_by_source_url_not_found(self, mock_get_client):
        """Test get_reference_document_by_source_url() when no document exists."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client

        doc = get_reference_document_by_source_url("https://unknown.com")

        assert doc is None

    @patch("src.db.repository.get_supabase_client")
    def test_get_reference_document_by_source_url_empty_url_returns_none(
        self, mock_get_client
    ):
        """Test get_reference_document_by_source_url() with empty URL returns None without querying."""
        doc = get_reference_document_by_source_url("")
        assert doc is None
        doc = get_reference_document_by_source_url("   ")
        assert doc is None


class TestSaveMessageHistory:
    """Test save_message_history() function."""

    @patch("src.db.repository.get_supabase_client")
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
            requires_escalation=False,
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

    @patch("src.db.repository.get_supabase_client")
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
            requires_escalation=True,
        )

        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["requires_escalation"] is True
        assert insert_call["confidence"] == 0.3

    @patch("src.db.repository.get_supabase_client")
    def test_save_message_history_with_user_profile_id(self, mock_get_client):
        """Test save_message_history() with user_profile_id."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        save_message_history(
            bot_id="bot-123",
            sender_id="user-456",
            message_text="Hello",
            response_text="Hi there",
            confidence=0.9,
            requires_escalation=False,
            user_profile_id="profile-uuid-789",
        )

        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["user_profile_id"] == "profile-uuid-789"


class TestUserProfileRepository:
    """Test user profile repository functions."""

    @patch("src.db.repository.get_supabase_client")
    def test_get_user_profile_found(self, mock_get_client):
        """get_user_profile returns profile when found."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "prof-1",
                "sender_id": "user-1",
                "page_id": "page-1",
                "first_name": "Jane",
                "last_name": "Doe",
            }
        ]
        chain = (
            mock_client.table.return_value.select.return_value.eq.return_value.execute
        )
        chain.return_value = mock_result
        mock_get_client.return_value = mock_client

        out = get_user_profile("user-1", "page-1")
        assert out is not None
        assert out["sender_id"] == "user-1"
        assert out["first_name"] == "Jane"

    @patch("src.db.repository.get_supabase_client")
    def test_get_user_profile_not_found(self, mock_get_client):
        """get_user_profile returns None when not found."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        chain = (
            mock_client.table.return_value.select.return_value.eq.return_value.execute
        )
        chain.return_value = mock_result
        mock_get_client.return_value = mock_client

        out = get_user_profile("user-1", "page-1")
        assert out is None

    @patch("src.db.repository.get_supabase_client")
    def test_create_user_profile(self, mock_get_client):
        """create_user_profile inserts and returns id."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "prof-new"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )
        mock_get_client.return_value = mock_client

        profile = UserProfileCreate(sender_id="user-1", page_id="page-1")
        uid = create_user_profile(profile)
        assert uid == "prof-new"
        mock_client.table.assert_called_with("user_profiles")
        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["sender_id"] == "user-1"
        assert insert_call["page_id"] == "page-1"

    @patch("src.db.repository.get_supabase_client")
    def test_update_user_profile(self, mock_get_client):
        """update_user_profile updates by sender_id."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "prof-1"}]
        chain = (
            mock_client.table.return_value.update.return_value.eq.return_value.execute
        )
        chain.return_value = mock_result
        mock_get_client.return_value = mock_client

        updates = UserProfileUpdate(
            location_lat=30.27,
            location_long=-97.74,
            location_title="Austin, TX",
        )
        ok = update_user_profile("user-1", "page-1", updates)
        assert ok is True
        mock_client.table.return_value.update.assert_called_once()
        update_call = mock_client.table.return_value.update.call_args[0][0]
        assert update_call["location_lat"] == 30.27
        assert update_call["location_title"] == "Austin, TX"

    @patch("src.db.repository.get_supabase_client")
    def test_upsert_user_profile(self, mock_get_client):
        """upsert_user_profile upserts on sender_id and returns full profile dict."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        # upsert_user_profile now returns the full profile dict, not just the ID
        mock_result.data = [{
            "id": "prof-upserted",
            "sender_id": "user-1",
            "page_id": "page-1",
            "first_name": "Jane",
            "locale": "en_US",
        }]
        chain = (
            mock_client.table.return_value.upsert.return_value.execute
        )
        chain.return_value = mock_result
        mock_get_client.return_value = mock_client

        profile = UserProfileCreate(
            sender_id="user-1",
            page_id="page-1",
            first_name="Jane",
            locale="en_US",
        )
        result = upsert_user_profile(profile)
        # Now returns full profile dict, not just ID
        assert result is not None
        assert result["id"] == "prof-upserted"
        assert result["sender_id"] == "user-1"
        assert result["first_name"] == "Jane"
        mock_client.table.assert_called_with("user_profiles")
        upsert_call = mock_client.table.return_value.upsert.call_args[0][0]
        assert upsert_call["sender_id"] == "user-1"
        assert upsert_call["first_name"] == "Jane"


class TestCreateTestSession:
    """Test create_test_session() function."""

    @patch("src.db.repository.get_supabase_client")
    def test_create_test_session_valid_inputs(self, mock_get_client):
        """Test create_test_session() with valid inputs."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "sess-456",
                "reference_doc_id": "doc-123",
                "source_url": "https://example.com",
                "tone": "Professional",
            }
        ]
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )
        mock_get_client.return_value = mock_client

        session_id = create_test_session(
            reference_doc_id="doc-123",
            source_url="https://example.com",
            tone="Professional",
        )

        assert session_id == "sess-456"
        mock_client.table.assert_called_with("test_sessions")
        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["reference_doc_id"] == "doc-123"
        assert insert_call["source_url"] == "https://example.com"
        assert insert_call["tone"] == "Professional"

    @patch("src.db.repository.get_supabase_client")
    def test_create_test_session_failure(self, mock_get_client):
        """Test error handling when test session creation fails."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(ValueError, match="Failed to create test session"):
            create_test_session(
                reference_doc_id="doc-123",
                source_url="https://example.com",
                tone="Friendly",
            )


class TestSaveTestMessage:
    """Test save_test_message() function."""

    @patch("src.db.repository.get_supabase_client")
    def test_save_test_message_all_fields(self, mock_get_client):
        """Test save_test_message() with all fields including escalation_reason."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"id": "msg-789"}]
        mock_client.table.return_value.insert.return_value.execute.return_value = (
            mock_result
        )
        mock_get_client.return_value = mock_client

        save_test_message(
            test_session_id="sess-456",
            user_message="Hello",
            response_text="Hi there",
            confidence=0.85,
            requires_escalation=True,
            escalation_reason="Out of scope",
        )

        mock_client.table.assert_called_with("test_messages")
        insert_call = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_call["test_session_id"] == "sess-456"
        assert insert_call["user_message"] == "Hello"
        assert insert_call["response_text"] == "Hi there"
        assert insert_call["confidence"] == 0.85
        assert insert_call["requires_escalation"] is True
        assert insert_call["escalation_reason"] == "Out of scope"
        assert "created_at" in insert_call

    @patch("src.db.repository.get_supabase_client")
    def test_save_test_message_does_not_raise_on_supabase_error(self, mock_get_client):
        """Test that save_test_message does not re-raise when Supabase fails."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.side_effect = (
            Exception("Supabase unavailable")
        )
        mock_get_client.return_value = mock_client

        save_test_message(
            test_session_id="sess-456",
            user_message="Hello",
            response_text="Hi",
            confidence=0.9,
            requires_escalation=False,
        )


# =============================================================================
# Bot Configuration Cache Tests
# =============================================================================


class TestBotConfigCache:
    """Test BotConfigCache class."""

    def test_cache_set_and_get(self):
        """Cache should store and retrieve configurations."""
        cache = BotConfigCache(ttl_seconds=60)

        config = BotConfiguration(
            id="bot-123",
            page_id="page-123",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="friendly",
            facebook_page_access_token="token",
            facebook_verify_token="verify",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )

        cache.set("page-123", config)

        retrieved = cache.get("page-123")
        assert retrieved is not None
        assert retrieved.id == "bot-123"
        assert retrieved.page_id == "page-123"

    def test_cache_miss_returns_none(self):
        """Cache should return None for missing entries."""
        cache = BotConfigCache(ttl_seconds=60)

        result = cache.get("nonexistent-page")
        assert result is None

    def test_cache_expiration(self):
        """Cache entries should expire after TTL."""
        # Use very short TTL for testing
        cache = BotConfigCache(ttl_seconds=0)  # Immediately expire

        config = BotConfiguration(
            id="bot-123",
            page_id="page-123",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="friendly",
            facebook_page_access_token="token",
            facebook_verify_token="verify",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )

        cache.set("page-123", config)
        # Small delay to ensure expiration
        time.sleep(0.01)

        result = cache.get("page-123")
        assert result is None

    def test_cache_invalidate(self):
        """Cache should remove entries on invalidate."""
        cache = BotConfigCache(ttl_seconds=60)

        config = BotConfiguration(
            id="bot-123",
            page_id="page-123",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="friendly",
            facebook_page_access_token="token",
            facebook_verify_token="verify",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )

        cache.set("page-123", config)
        assert cache.get("page-123") is not None

        cache.invalidate("page-123")
        assert cache.get("page-123") is None

    def test_cache_invalidate_nonexistent_is_noop(self):
        """Invalidating nonexistent entry should not raise."""
        cache = BotConfigCache(ttl_seconds=60)
        # Should not raise
        cache.invalidate("nonexistent-page")

    def test_cache_clear(self):
        """Cache clear should remove all entries."""
        cache = BotConfigCache(ttl_seconds=60)

        for i in range(3):
            config = BotConfiguration(
                id=f"bot-{i}",
                page_id=f"page-{i}",
                website_url="https://example.com",
                reference_doc_id=f"doc-{i}",
                tone="friendly",
                facebook_page_access_token="token",
                facebook_verify_token="verify",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True,
            )
            cache.set(f"page-{i}", config)

        assert cache.size == 3

        cache.clear()
        assert cache.size == 0
        assert cache.get("page-0") is None

    def test_cache_size_property(self):
        """Size property should return number of entries."""
        cache = BotConfigCache(ttl_seconds=60)
        assert cache.size == 0

        config = BotConfiguration(
            id="bot-123",
            page_id="page-123",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="friendly",
            facebook_page_access_token="token",
            facebook_verify_token="verify",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )

        cache.set("page-123", config)
        assert cache.size == 1


class TestBotConfigCacheIntegration:
    """Test cache integration with repository functions."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_bot_config_cache()

    def teardown_method(self):
        """Clean up cache after each test."""
        reset_bot_config_cache()

    @patch("src.db.repository.get_supabase_client")
    def test_get_bot_config_caches_result(self, mock_get_client):
        """First call should hit DB, second should use cache."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "bot-123",
            "page_id": "page-123",
            "website_url": "https://example.com",
            "reference_doc_id": "doc-123",
            "tone": "friendly",
            "facebook_page_access_token": "token",
            "facebook_verify_token": "verify",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "is_active": True,
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client

        # First call - should hit DB
        result1 = get_bot_configuration_by_page_id("page-123")
        assert result1 is not None
        assert result1.id == "bot-123"

        # Second call - should use cache (DB not called again)
        mock_client.reset_mock()
        result2 = get_bot_configuration_by_page_id("page-123")
        assert result2 is not None
        assert result2.id == "bot-123"

        # Verify DB was not called on second request
        mock_client.table.assert_not_called()

    @patch("src.db.repository.get_supabase_client")
    def test_get_bot_config_not_found_not_cached(self, mock_get_client):
        """Not-found results should not be cached."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client

        # First call - returns None
        result1 = get_bot_configuration_by_page_id("nonexistent-page")
        assert result1 is None

        # Second call - should still hit DB (None not cached)
        result2 = get_bot_configuration_by_page_id("nonexistent-page")
        assert result2 is None

        # Verify DB was called twice
        assert mock_client.table.call_count == 2

    @patch("src.db.repository.get_supabase_client")
    @patch("src.db.repository.link_reference_document_to_bot")
    def test_create_bot_config_invalidates_cache(
        self, mock_link, mock_get_client
    ):
        """Creating a bot config should invalidate cache for that page_id."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "bot-new",
            "page_id": "page-123",
            "website_url": "https://example.com",
            "reference_doc_id": "doc-123",
            "tone": "friendly",
            "facebook_page_access_token": "token",
            "facebook_verify_token": "verify",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "is_active": True,
        }]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client

        # Pre-populate cache
        cache = get_bot_config_cache()
        old_config = BotConfiguration(
            id="bot-old",
            page_id="page-123",
            website_url="https://old.com",
            reference_doc_id="doc-old",
            tone="professional",
            facebook_page_access_token="old-token",
            facebook_verify_token="old-verify",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )
        cache.set("page-123", old_config)

        # Create new config (should invalidate cache)
        from src.models.config_models import BotConfigurationCreate

        new_config = BotConfigurationCreate(
            page_id="page-123",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="friendly",
            facebook_page_access_token="token",
            facebook_verify_token="verify",
        )
        create_bot_configuration(config=new_config)

        # Cache should be invalidated
        assert cache.get("page-123") is None
