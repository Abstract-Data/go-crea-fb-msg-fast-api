"""Message processing orchestration service.

This module extracts the message processing workflow from webhook.py into a
dedicated service, following the Single Responsibility Principle. The webhook
handler now focuses on HTTP concerns while MessageProcessor handles:
- User profile management (fetch/create)
- Building agent context
- Generating AI responses
- Response personalization
- Message history persistence

Benefits:
- Better testability via dependency injection
- Cleaner separation of concerns
- Easier to add features like message queuing or retry logic
"""

from __future__ import annotations

import logging
import random
from typing import Callable

import logfire

from src.db.repository import (
    get_bot_configuration_by_page_id,
    get_reference_document,
    get_user_profile,
    save_message_history,
    upsert_user_profile,
)
from src.models.agent_models import AgentContext, AgentResponse
from src.models.config_models import BotConfiguration
from src.models.message_models import MessageHistoryCreate
from src.models.user_models import UserProfileCreate
from src.services.agent_service import MessengerAgentService, get_agent_service
from src.services.messaging_protocol import (
    MessagingService,
    get_messaging_service,
)

logger = logging.getLogger(__name__)


class MessageProcessorError(Exception):
    """Base exception for MessageProcessor errors."""

    pass


class BotConfigNotFoundError(MessageProcessorError):
    """Raised when bot configuration is not found."""

    pass


class ReferenceDocNotFoundError(MessageProcessorError):
    """Raised when reference document is not found."""

    pass


class MessageProcessor:
    """Orchestrate the end-to-end message processing workflow.

    This service handles the complete message processing pipeline:
    1. Retrieve bot configuration
    2. Ensure user profile exists (fetch from FB if needed)
    3. Retrieve reference document
    4. Build agent context
    5. Generate AI response
    6. Personalize response
    7. Send message via messaging service
    8. Save message history

    The processor uses dependency injection for the agent and messaging services,
    making it easy to test and swap implementations.

    Example:
        >>> processor = MessageProcessor()
        >>> await processor.process("page123", "user456", "Hello!")

        # With custom services for testing:
        >>> mock_agent = MockAgentService()
        >>> mock_messaging = MockMessagingService()
        >>> processor = MessageProcessor(
        ...     agent_service=mock_agent,
        ...     messaging_service_factory=lambda token: mock_messaging,
        ... )
    """

    def __init__(
        self,
        agent_service: MessengerAgentService | None = None,
        messaging_service_factory: (Callable[[str], MessagingService] | None) = None,
    ):
        """Initialize the message processor.

        Args:
            agent_service: Optional agent service for generating responses.
                           Uses get_agent_service() if not provided.
            messaging_service_factory: Optional factory function to create
                                       MessagingService instances. Receives
                                       page_access_token and returns a service.
                                       Uses get_messaging_service() if not provided.
        """
        self._agent_service = agent_service
        self._messaging_service_factory = (
            messaging_service_factory or get_messaging_service
        )

    def _get_agent_service(self) -> MessengerAgentService:
        """Get or create the agent service instance."""
        if self._agent_service is None:
            self._agent_service = get_agent_service()
        return self._agent_service

    async def process(
        self,
        page_id: str,
        sender_id: str,
        message_text: str,
    ) -> None:
        """Process incoming message end-to-end.

        Orchestrates the complete message processing workflow from receiving
        the message to sending the response and saving history.

        Args:
            page_id: Facebook Page ID
            sender_id: Facebook user ID (PSID) of the message sender
            message_text: The sanitized message text to process

        Raises:
            BotConfigNotFoundError: If no bot configuration found for page_id
            ReferenceDocNotFoundError: If reference document not found
        """
        # Get bot configuration
        bot_config = get_bot_configuration_by_page_id(page_id)
        if not bot_config:
            logfire.error("No bot configuration found", page_id=page_id)
            raise BotConfigNotFoundError(
                f"No bot configuration found for page_id: {page_id}"
            )

        # Create messaging service for this bot
        messaging_service = self._messaging_service_factory(
            bot_config.facebook_page_access_token
        )

        # Ensure user profile exists
        user_profile = await self._ensure_user_profile(
            sender_id=sender_id,
            page_id=page_id,
            messaging_service=messaging_service,
        )

        # Get reference document
        ref_doc = get_reference_document(bot_config.reference_doc_id)
        if not ref_doc:
            logfire.error(
                "No reference document found",
                doc_id=bot_config.reference_doc_id,
            )
            raise ReferenceDocNotFoundError(
                f"No reference document found: {bot_config.reference_doc_id}"
            )

        # Build agent context
        context = self._build_context(bot_config, ref_doc, user_profile)

        # Generate response
        agent_service = self._get_agent_service()
        response = await agent_service.respond(context, message_text)

        # Personalize and send response
        personalized = self._personalize_response(response, user_profile)
        await messaging_service.send_message(
            recipient_id=sender_id,
            text=personalized,
        )

        # Save message history using parameter object
        message_history = MessageHistoryCreate(
            bot_id=bot_config.id,
            sender_id=sender_id,
            message_text=message_text,
            response_text=personalized,
            confidence=response.confidence,
            requires_escalation=response.requires_escalation,
            user_profile_id=user_profile.get("id") if user_profile else None,
        )
        save_message_history(message_history)

        logfire.info(
            "Message processed",
            page_id=page_id,
            sender_id=sender_id,
            user_name=user_profile.get("first_name") if user_profile else None,
            user_location=user_profile.get("location_title") if user_profile else None,
            confidence=response.confidence,
            escalation=response.requires_escalation,
        )

    async def _ensure_user_profile(
        self,
        sender_id: str,
        page_id: str,
        messaging_service: MessagingService,
    ) -> dict | None:
        """Get or create user profile.

        First checks if a profile exists in the database. If not, fetches
        user info from Facebook and creates a new profile.

        Args:
            sender_id: Facebook user ID (PSID)
            page_id: Facebook Page ID
            messaging_service: Service to fetch user info from Facebook

        Returns:
            User profile dict or None if profile creation failed
        """
        profile = get_user_profile(sender_id, page_id)
        if profile:
            return profile

        # Fetch from Facebook and create
        logger.info("New user %s, fetching profile from Facebook", sender_id)
        fb_info = await messaging_service.get_user_info(sender_id)
        if fb_info:
            new_profile = UserProfileCreate(
                sender_id=sender_id,
                page_id=page_id,
                first_name=fb_info.first_name,
                last_name=fb_info.last_name,
                profile_pic=fb_info.profile_pic,
                locale=fb_info.locale,
                timezone=fb_info.timezone,
            )
            # upsert_user_profile returns the full profile
            return upsert_user_profile(new_profile)
        return None

    def _build_context(
        self,
        bot_config: BotConfiguration,
        ref_doc: dict,
        user_profile: dict | None,
    ) -> AgentContext:
        """Build agent context from components.

        Assembles all the context needed by the agent to generate a response,
        including reference document, tone, and user information.

        Args:
            bot_config: Bot configuration with settings
            ref_doc: Reference document dict with 'content' key
            user_profile: User profile dict or None

        Returns:
            AgentContext ready for the agent service
        """
        return AgentContext(
            bot_config_id=bot_config.id,
            reference_doc_id=bot_config.reference_doc_id,
            reference_doc=ref_doc["content"],
            tone=bot_config.tone,
            recent_messages=[],  # TODO: Implement message history retrieval
            tenant_id=getattr(bot_config, "tenant_id", None),
            user_name=user_profile.get("first_name") if user_profile else None,
            user_location=user_profile.get("location_title") if user_profile else None,
        )

    def _personalize_response(
        self,
        response: AgentResponse,
        user_profile: dict | None,
    ) -> str:
        """Add personalization to response.

        Occasionally adds a personal greeting when:
        - User name is known
        - Response confidence is high (>0.8)
        - Response doesn't already start with user's name
        - Random chance (20%)

        Args:
            response: Agent response with message and confidence
            user_profile: User profile dict or None

        Returns:
            Personalized message text
        """
        text = response.message
        user_name = user_profile.get("first_name") if user_profile else None

        if user_name and response.confidence > 0.8:
            if not text.startswith(user_name) and random.random() < 0.2:
                text = f"Hi {user_name}! {text}"

        return text


def get_message_processor(
    agent_service: MessengerAgentService | None = None,
    messaging_service_factory: Callable[[str], MessagingService] | None = None,
) -> MessageProcessor:
    """Factory function to create a MessageProcessor instance.

    Args:
        agent_service: Optional agent service instance
        messaging_service_factory: Optional factory for messaging services

    Returns:
        Configured MessageProcessor instance
    """
    return MessageProcessor(
        agent_service=agent_service,
        messaging_service_factory=messaging_service_factory,
    )
