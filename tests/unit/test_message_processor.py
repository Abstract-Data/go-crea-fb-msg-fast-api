"""Unit tests for MessageProcessor service.

Note: Most fixtures used in this file (mock_bot_config, mock_ref_doc,
mock_user_profile, mock_agent_response, mock_agent_service, mock_messaging_service)
are centralized in conftest.py for reuse across test files.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.agent_models import AgentContext, AgentResponse
from src.models.user_models import FacebookUserInfo
from src.services.message_processor import (
    BotConfigNotFoundError,
    MessageProcessor,
    ReferenceDocNotFoundError,
    get_message_processor,
)


# All fixtures used in this file are now centralized in conftest.py


class TestMessageProcessor:
    """Test MessageProcessor service."""

    @pytest.mark.asyncio
    @patch("src.services.message_processor.save_message_history")
    @patch("src.services.message_processor.get_reference_document")
    @patch("src.services.message_processor.get_user_profile")
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_process_existing_user_success(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_save_history,
        mock_bot_config,
        mock_ref_doc,
        mock_user_profile,
        mock_agent_service,
        mock_messaging_service,
    ):
        """Test successful processing with existing user profile."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = mock_user_profile
        mock_get_ref.return_value = mock_ref_doc

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        await processor.process(
            page_id="page-1",
            sender_id="user-1",
            message_text="Hello!",
        )

        # Verify bot config lookup
        mock_get_bot.assert_called_once_with("page-1")

        # Verify user profile lookup
        mock_get_profile.assert_called_once_with("user-1", "page-1")

        # Verify reference document lookup
        mock_get_ref.assert_called_once_with("doc-1")

        # Verify agent was called
        mock_agent_service.respond.assert_called_once()
        context = mock_agent_service.respond.call_args[0][0]
        assert isinstance(context, AgentContext)
        assert context.user_name == "Jane"
        assert context.user_location == "Austin, TX"
        assert context.tone == "friendly"
        assert context.reference_doc == "# Reference\nTest content for the bot."

        # Verify message was sent
        mock_messaging_service.send_message.assert_called_once()
        call = mock_messaging_service.send_message.call_args
        assert call.kwargs["recipient_id"] == "user-1"
        assert "How can I help" in call.kwargs["text"]

        # Verify history was saved
        mock_save_history.assert_called_once()
        saved_msg = mock_save_history.call_args[0][0]
        assert saved_msg.bot_id == "bot-1"
        assert saved_msg.sender_id == "user-1"
        assert saved_msg.message_text == "Hello!"
        assert saved_msg.user_profile_id == "profile-1"

    @pytest.mark.asyncio
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_process_no_bot_config_raises(
        self,
        mock_get_bot,
        mock_agent_service,
        mock_messaging_service,
    ):
        """Test that missing bot config raises BotConfigNotFoundError."""
        mock_get_bot.return_value = None

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        with pytest.raises(BotConfigNotFoundError) as exc_info:
            await processor.process(
                page_id="unknown-page",
                sender_id="user-1",
                message_text="Hello!",
            )

        assert "unknown-page" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("src.services.message_processor.get_reference_document")
    @patch("src.services.message_processor.get_user_profile")
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_process_no_ref_doc_raises(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_bot_config,
        mock_user_profile,
        mock_agent_service,
        mock_messaging_service,
    ):
        """Test that missing reference document raises ReferenceDocNotFoundError."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = mock_user_profile
        mock_get_ref.return_value = None

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        with pytest.raises(ReferenceDocNotFoundError) as exc_info:
            await processor.process(
                page_id="page-1",
                sender_id="user-1",
                message_text="Hello!",
            )

        assert "doc-1" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("src.services.message_processor.save_message_history")
    @patch("src.services.message_processor.upsert_user_profile")
    @patch("src.services.message_processor.get_reference_document")
    @patch("src.services.message_processor.get_user_profile")
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_process_new_user_creates_profile(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_upsert,
        mock_save_history,
        mock_bot_config,
        mock_ref_doc,
        mock_user_profile,
        mock_agent_service,
    ):
        """Test that new users get their profile created from Facebook."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = None  # New user
        mock_get_ref.return_value = mock_ref_doc
        mock_upsert.return_value = mock_user_profile

        # Create mock messaging service that returns user info
        mock_messaging_service = MagicMock()
        mock_messaging_service.send_message = AsyncMock(return_value=True)
        mock_messaging_service.get_user_info = AsyncMock(
            return_value=FacebookUserInfo(
                id="user-1",
                first_name="Jane",
                last_name="Doe",
                locale="en_US",
                timezone=-6,
            )
        )

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        await processor.process(
            page_id="page-1",
            sender_id="user-1",
            message_text="Hello!",
        )

        # Verify Facebook API was called to get user info
        mock_messaging_service.get_user_info.assert_called_once_with("user-1")

        # Verify profile was upserted
        mock_upsert.assert_called_once()
        profile_create = mock_upsert.call_args[0][0]
        assert profile_create.sender_id == "user-1"
        assert profile_create.page_id == "page-1"
        assert profile_create.first_name == "Jane"
        assert profile_create.last_name == "Doe"

        # Verify agent context uses the created profile
        context = mock_agent_service.respond.call_args[0][0]
        assert context.user_name == "Jane"

    @pytest.mark.asyncio
    @patch("src.services.message_processor.save_message_history")
    @patch("src.services.message_processor.get_reference_document")
    @patch("src.services.message_processor.get_user_profile")
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_personalize_response_high_confidence(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_save_history,
        mock_bot_config,
        mock_ref_doc,
        mock_user_profile,
        mock_messaging_service,
    ):
        """Test response personalization with high confidence (may add name)."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = mock_user_profile
        mock_get_ref.return_value = mock_ref_doc

        # Create agent that returns high confidence
        mock_agent_service = MagicMock()
        mock_agent_service.respond = AsyncMock(
            return_value=AgentResponse(
                message="Hello! How can I help?",
                confidence=0.95,  # High confidence
                requires_escalation=False,
            )
        )

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        # Run multiple times to potentially hit the 20% personalization chance
        responses_with_name = 0
        for _ in range(50):
            mock_messaging_service.send_message.reset_mock()
            await processor.process(
                page_id="page-1",
                sender_id="user-1",
                message_text="Hello!",
            )
            sent_text = mock_messaging_service.send_message.call_args.kwargs["text"]
            if sent_text.startswith("Hi Jane!"):
                responses_with_name += 1

        # With 20% chance over 50 runs, we'd expect ~10 personalized responses
        # Allow some variance (at least 2 and no more than 25)
        assert 2 <= responses_with_name <= 25

    @pytest.mark.asyncio
    @patch("src.services.message_processor.save_message_history")
    @patch("src.services.message_processor.get_reference_document")
    @patch("src.services.message_processor.get_user_profile")
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_no_personalize_low_confidence(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_save_history,
        mock_bot_config,
        mock_ref_doc,
        mock_user_profile,
        mock_messaging_service,
    ):
        """Test that low confidence responses are not personalized."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = mock_user_profile
        mock_get_ref.return_value = mock_ref_doc

        # Create agent that returns low confidence
        mock_agent_service = MagicMock()
        mock_agent_service.respond = AsyncMock(
            return_value=AgentResponse(
                message="Hello! How can I help?",
                confidence=0.5,  # Low confidence
                requires_escalation=False,
            )
        )

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        # Run multiple times - none should be personalized
        for _ in range(20):
            mock_messaging_service.send_message.reset_mock()
            await processor.process(
                page_id="page-1",
                sender_id="user-1",
                message_text="Hello!",
            )
            sent_text = mock_messaging_service.send_message.call_args.kwargs["text"]
            assert not sent_text.startswith("Hi Jane!")

    @pytest.mark.asyncio
    @patch("src.services.message_processor.save_message_history")
    @patch("src.services.message_processor.get_reference_document")
    @patch("src.services.message_processor.get_user_profile")
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_no_user_profile_still_processes(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_save_history,
        mock_bot_config,
        mock_ref_doc,
        mock_agent_response,
        mock_agent_service,
    ):
        """Test that processing works even if user profile cannot be created."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = None  # No existing profile
        mock_get_ref.return_value = mock_ref_doc

        # Messaging service returns None for user info
        mock_messaging_service = MagicMock()
        mock_messaging_service.send_message = AsyncMock(return_value=True)
        mock_messaging_service.get_user_info = AsyncMock(return_value=None)

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        await processor.process(
            page_id="page-1",
            sender_id="user-1",
            message_text="Hello!",
        )

        # Agent should still be called with None for user_name
        context = mock_agent_service.respond.call_args[0][0]
        assert context.user_name is None
        assert context.user_location is None

        # Message should still be sent
        mock_messaging_service.send_message.assert_called_once()

        # History should be saved with None user_profile_id
        mock_save_history.assert_called_once()
        saved_msg = mock_save_history.call_args[0][0]
        assert saved_msg.user_profile_id is None


class TestMessageProcessorFactory:
    """Test get_message_processor factory function."""

    def test_factory_returns_processor(self):
        """Test that factory returns a MessageProcessor instance."""
        processor = get_message_processor()
        assert isinstance(processor, MessageProcessor)

    def test_factory_accepts_custom_agent(self):
        """Test that factory accepts custom agent service."""
        mock_agent = MagicMock()
        processor = get_message_processor(agent_service=mock_agent)
        assert processor._agent_service == mock_agent

    def test_factory_accepts_custom_messaging_factory(self):
        """Test that factory accepts custom messaging factory."""
        mock_factory = MagicMock()
        processor = get_message_processor(messaging_service_factory=mock_factory)
        assert processor._messaging_service_factory == mock_factory


class TestMessageProcessorContextBuilding:
    """Test AgentContext building in MessageProcessor."""

    @pytest.mark.asyncio
    @patch("src.services.message_processor.save_message_history")
    @patch("src.services.message_processor.get_reference_document")
    @patch("src.services.message_processor.get_user_profile")
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_context_includes_all_fields(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_save_history,
        mock_agent_service,
        mock_messaging_service,
    ):
        """Test that AgentContext is built with all required fields."""
        mock_bot_config = MagicMock()
        mock_bot_config.id = "bot-1"
        mock_bot_config.page_id = "page-1"
        mock_bot_config.reference_doc_id = "doc-1"
        mock_bot_config.tone = "professional"
        mock_bot_config.facebook_page_access_token = "token"
        mock_bot_config.tenant_id = "tenant-123"

        mock_user_profile = {
            "id": "profile-1",
            "sender_id": "user-1",
            "first_name": "John",
            "location_title": "New York, NY",
        }

        mock_ref_doc = {
            "id": "doc-1",
            "content": "Test reference content here.",
        }

        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = mock_user_profile
        mock_get_ref.return_value = mock_ref_doc

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        await processor.process(
            page_id="page-1",
            sender_id="user-1",
            message_text="Test message",
        )

        # Verify context was built correctly
        context = mock_agent_service.respond.call_args[0][0]
        assert context.bot_config_id == "bot-1"
        assert context.reference_doc_id == "doc-1"
        assert context.reference_doc == "Test reference content here."
        assert context.tone == "professional"
        assert context.tenant_id == "tenant-123"
        assert context.user_name == "John"
        assert context.user_location == "New York, NY"
        assert context.recent_messages == []  # TODO: implement message history


class TestMessageProcessorHistorySaving:
    """Test message history saving in MessageProcessor."""

    @pytest.mark.asyncio
    @patch("src.services.message_processor.save_message_history")
    @patch("src.services.message_processor.get_reference_document")
    @patch("src.services.message_processor.get_user_profile")
    @patch("src.services.message_processor.get_bot_configuration_by_page_id")
    async def test_history_includes_escalation_info(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_save_history,
        mock_bot_config,
        mock_ref_doc,
        mock_user_profile,
        mock_messaging_service,
    ):
        """Test that history includes escalation information."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = mock_user_profile
        mock_get_ref.return_value = mock_ref_doc

        # Agent returns escalation required
        mock_agent_service = MagicMock()
        mock_agent_service.respond = AsyncMock(
            return_value=AgentResponse(
                message="I need to escalate this to a human.",
                confidence=0.3,
                requires_escalation=True,
                escalation_reason="Complex query",
            )
        )

        processor = MessageProcessor(
            agent_service=mock_agent_service,
            messaging_service_factory=lambda token: mock_messaging_service,
        )

        await processor.process(
            page_id="page-1",
            sender_id="user-1",
            message_text="Complex question",
        )

        # Verify history includes escalation info
        mock_save_history.assert_called_once()
        saved_msg = mock_save_history.call_args[0][0]
        assert saved_msg.confidence == 0.3
        assert saved_msg.requires_escalation is True
