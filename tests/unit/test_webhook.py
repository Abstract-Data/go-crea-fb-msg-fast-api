"""Unit tests for webhook handlers (process_message, process_location)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.webhook import (
    process_message,
    process_location,
)
from src.models.agent_models import AgentResponse


@pytest.fixture
def mock_bot_config():
    """Minimal bot config for webhook tests."""
    config = MagicMock()
    config.id = "bot-1"
    config.page_id = "page-1"
    config.reference_doc_id = "doc-1"
    config.tone = "friendly"
    config.facebook_page_access_token = "token"
    config.tenant_id = None
    return config


@pytest.fixture
def mock_ref_doc():
    return {"id": "doc-1", "content": "# Reference\nTest content."}


@pytest.fixture
def mock_user_profile():
    return {
        "id": "profile-1",
        "sender_id": "user-1",
        "page_id": "page-1",
        "first_name": "Jane",
        "last_name": "Doe",
        "location_title": "Austin, TX",
    }


class TestProcessMessage:
    """Test process_message handler."""

    @pytest.mark.asyncio
    @patch("src.api.webhook.save_message_history")
    @patch("src.api.webhook.send_message", new_callable=AsyncMock)
    @patch("src.api.webhook.MessengerAgentService")
    @patch("src.api.webhook.get_reference_document")
    @patch("src.api.webhook.get_user_profile")
    @patch("src.api.webhook.get_bot_configuration_by_page_id")
    async def test_process_message_existing_profile(
        self,
        mock_get_bot,
        mock_get_profile,
        mock_get_ref,
        mock_agent_cls,
        mock_send,
        mock_save,
        mock_bot_config,
        mock_ref_doc,
        mock_user_profile,
    ):
        """With existing user profile, no fetch; user_name/location passed to agent."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.return_value = mock_user_profile
        mock_get_ref.return_value = mock_ref_doc

        agent_instance = MagicMock()
        agent_instance.respond = AsyncMock(
            return_value=AgentResponse(
                message="Hi! How can I help?",
                confidence=0.9,
                requires_escalation=False,
            )
        )
        mock_agent_cls.return_value = agent_instance

        await process_message(
            page_id="page-1",
            sender_id="user-1",
            message_text="Hello",
        )

        mock_get_profile.assert_called_once_with("user-1", "page-1")
        mock_get_ref.assert_called_once_with("doc-1")
        mock_send.assert_called_once()
        call = mock_send.call_args
        assert call.kwargs["recipient_id"] == "user-1"
        assert "How can I help" in call.kwargs["text"]

        mock_save.assert_called_once()
        save_kw = mock_save.call_args[1]
        assert save_kw["user_profile_id"] == "profile-1"
        assert save_kw["sender_id"] == "user-1"

        # Agent context should include user_name and user_location
        ctx = agent_instance.respond.call_args[0][0]
        assert ctx.user_name == "Jane"
        assert ctx.user_location == "Austin, TX"

    @pytest.mark.asyncio
    @patch("src.api.webhook.save_message_history")
    @patch("src.api.webhook.send_message", new_callable=AsyncMock)
    @patch("src.api.webhook.MessengerAgentService")
    @patch("src.api.webhook.get_reference_document")
    @patch("src.api.webhook.get_user_profile")
    @patch("src.api.webhook.get_user_info", new_callable=AsyncMock)
    @patch("src.api.webhook.upsert_user_profile")
    @patch("src.api.webhook.get_bot_configuration_by_page_id")
    async def test_process_message_new_user_fetches_profile(
        self,
        mock_get_bot,
        mock_upsert,
        mock_get_info,
        mock_get_profile,
        mock_get_ref,
        mock_agent_cls,
        mock_send,
        mock_save,
        mock_bot_config,
        mock_ref_doc,
        mock_user_profile,
    ):
        """New user triggers get_user_info, upsert, then proceed."""
        mock_get_bot.return_value = mock_bot_config
        mock_get_profile.side_effect = [None, mock_user_profile]
        mock_get_ref.return_value = mock_ref_doc
        mock_upsert.return_value = "profile-1"

        from src.models.user_models import FacebookUserInfo

        mock_get_info.return_value = FacebookUserInfo(
            id="user-1",
            first_name="Jane",
            last_name="Doe",
            locale="en_US",
            timezone=-6,
        )

        agent_instance = MagicMock()
        agent_instance.respond = AsyncMock(
            return_value=AgentResponse(
                message="Welcome!",
                confidence=0.85,
                requires_escalation=False,
            )
        )
        mock_agent_cls.return_value = agent_instance

        await process_message(
            page_id="page-1",
            sender_id="user-1",
            message_text="Hi",
        )

        mock_get_info.assert_called_once_with(
            page_access_token="token",
            user_id="user-1",
        )
        mock_upsert.assert_called_once()
        mock_save.assert_called_once()
        assert mock_save.call_args[1]["user_profile_id"] == "profile-1"

    @pytest.mark.asyncio
    @patch("src.api.webhook.get_bot_configuration_by_page_id")
    async def test_process_message_no_bot_config(self, mock_get_bot):
        """No bot config -> early return, no agent/send/save."""
        mock_get_bot.return_value = None
        await process_message(
            page_id="page-999",
            sender_id="user-1",
            message_text="Hello",
        )
        mock_get_bot.assert_called_once_with("page-999")


class TestProcessLocation:
    """Test process_location handler."""

    @pytest.mark.asyncio
    @patch("src.api.webhook.send_message", new_callable=AsyncMock)
    @patch("src.api.webhook.get_bot_configuration_by_page_id")
    @patch("src.api.webhook.update_user_profile")
    async def test_process_location_success(
        self,
        mock_update,
        mock_get_bot,
        mock_send,
        mock_bot_config,
    ):
        """Valid location -> update profile, send ack."""
        mock_update.return_value = True
        mock_get_bot.return_value = mock_bot_config

        location = {
            "coordinates": {"lat": 30.27, "long": -97.74},
            "title": "Austin, TX",
            "address": "123 Main St",
        }

        await process_location(
            page_id="page-1",
            sender_id="user-1",
            location=location,
        )

        mock_update.assert_called_once()
        updates = mock_update.call_args[0][2]
        assert updates.location_lat == 30.27
        assert updates.location_long == -97.74
        assert updates.location_title == "Austin, TX"
        assert updates.location_address == "123 Main St"

        mock_send.assert_called_once()
        assert "Austin, TX" in mock_send.call_args[1]["text"]
        assert "Thanks for sharing your location" in mock_send.call_args[1]["text"]

    @pytest.mark.asyncio
    @patch("src.api.webhook.send_message", new_callable=AsyncMock)
    @patch("src.api.webhook.update_user_profile")
    async def test_process_location_invalid_coords(self, mock_update, mock_send):
        """Missing lat/long -> no update, no ack."""
        location = {"coordinates": {}}

        await process_location(
            page_id="page-1",
            sender_id="user-1",
            location=location,
        )

        mock_update.assert_not_called()
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.api.webhook.send_message", new_callable=AsyncMock)
    @patch("src.api.webhook.get_bot_configuration_by_page_id")
    @patch("src.api.webhook.update_user_profile")
    async def test_process_location_lng_alias(self, mock_update, mock_get_bot, mock_send):
        """Coordinates with 'lng' instead of 'long'."""
        mock_update.return_value = True
        mock_get_bot.return_value = MagicMock()
        mock_get_bot.return_value.facebook_page_access_token = "token"

        location = {
            "coordinates": {"lat": 40.7, "lng": -74.0},
            "title": "New York, NY",
        }

        await process_location(
            page_id="page-1",
            sender_id="user-1",
            location=location,
        )

        mock_update.assert_called_once()
        updates = mock_update.call_args[0][2]
        assert updates.location_lat == 40.7
        assert updates.location_long == -74.0
        assert updates.location_title == "New York, NY"

    @pytest.mark.asyncio
    @patch("src.api.webhook.send_message", new_callable=AsyncMock)
    @patch("src.api.webhook.get_bot_configuration_by_page_id")
    @patch("src.api.webhook.update_user_profile")
    async def test_process_location_update_fails_no_ack(
        self, mock_update, mock_get_bot, mock_send
    ):
        """update_user_profile fails -> no ack sent."""
        mock_update.return_value = False

        location = {
            "coordinates": {"lat": 30.27, "long": -97.74},
            "title": "Austin, TX",
        }

        await process_location(
            page_id="page-1",
            sender_id="user-1",
            location=location,
        )

        mock_send.assert_not_called()
