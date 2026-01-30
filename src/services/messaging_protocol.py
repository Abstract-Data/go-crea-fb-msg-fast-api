"""Messaging abstraction protocols for decoupling from Facebook API.

This module provides a Protocol-based abstraction for messaging services,
allowing the application to:
- Easily swap Facebook for other messaging platforms (Slack, WhatsApp, etc.)
- Mock messaging in tests without complex httpx mocking
- Support dependency injection for cleaner architecture
"""

from typing import Protocol

import logfire

from src.models.user_models import FacebookUserInfo


class MessagingService(Protocol):
    """Protocol for sending messages and fetching user info.

    Implementations must provide these methods to handle messaging operations.
    Using a Protocol allows type checking while supporting duck typing and
    easy test mocking.
    """

    async def send_message(
        self,
        recipient_id: str,
        text: str,
    ) -> bool:
        """Send message to recipient.

        Args:
            recipient_id: Platform-specific user identifier
            text: Message text to send

        Returns:
            True if message sent successfully, False otherwise
        """
        ...

    async def get_user_info(
        self,
        user_id: str,
    ) -> FacebookUserInfo | None:
        """Get user profile information.

        Args:
            user_id: Platform-specific user identifier

        Returns:
            User profile info or None if not found/error
        """
        ...


class FacebookMessagingService:
    """Facebook Messenger implementation of MessagingService.

    Wraps the existing facebook_service functions while providing
    the MessagingService protocol interface.

    Example:
        >>> service = FacebookMessagingService(page_access_token="...")
        >>> await service.send_message("user123", "Hello!")
        True
        >>> user = await service.get_user_info("user123")
        >>> user.first_name
        'John'
    """

    def __init__(self, page_access_token: str):
        """Initialize with Facebook Page access token.

        Args:
            page_access_token: Facebook Page access token for API calls
        """
        if not page_access_token:
            raise ValueError("page_access_token is required")
        self._token = page_access_token

    async def send_message(self, recipient_id: str, text: str) -> bool:
        """Send message via Facebook Messenger.

        Args:
            recipient_id: Facebook user ID (PSID) to send message to
            text: Message text to send

        Returns:
            True if message sent successfully, False on error
        """
        from src.services.facebook_service import send_message

        try:
            await send_message(
                page_access_token=self._token,
                recipient_id=recipient_id,
                text=text,
            )
            return True
        except Exception as e:
            logfire.error(
                "FacebookMessagingService.send_message failed",
                recipient_id=recipient_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def get_user_info(self, user_id: str) -> FacebookUserInfo | None:
        """Get user info from Facebook Graph API.

        Args:
            user_id: Facebook user ID (PSID)

        Returns:
            FacebookUserInfo with profile data, or None on error
        """
        from src.services.facebook_service import get_user_info

        return await get_user_info(
            page_access_token=self._token,
            user_id=user_id,
        )


class MockMessagingService:
    """Mock implementation for testing.

    Allows tests to verify messaging behavior without making real API calls.

    Example:
        >>> service = MockMessagingService()
        >>> await service.send_message("user123", "Test message")
        True
        >>> service.sent_messages
        [('user123', 'Test message')]
    """

    def __init__(
        self,
        user_info: FacebookUserInfo | None = None,
        should_fail_send: bool = False,
    ):
        """Initialize mock service.

        Args:
            user_info: User info to return from get_user_info (None by default)
            should_fail_send: Whether send_message should return False
        """
        self._user_info = user_info
        self._should_fail_send = should_fail_send
        self.sent_messages: list[tuple[str, str]] = []
        self.get_user_info_calls: list[str] = []

    async def send_message(self, recipient_id: str, text: str) -> bool:
        """Record sent message and return configured result."""
        self.sent_messages.append((recipient_id, text))
        return not self._should_fail_send

    async def get_user_info(self, user_id: str) -> FacebookUserInfo | None:
        """Record call and return configured user info."""
        self.get_user_info_calls.append(user_id)
        return self._user_info


def get_messaging_service(page_access_token: str) -> FacebookMessagingService:
    """Factory function to get a MessagingService implementation.

    Currently returns FacebookMessagingService. This factory allows
    future extension to support other platforms or conditional logic.

    Args:
        page_access_token: Facebook Page access token

    Returns:
        MessagingService implementation (currently Facebook)
    """
    return FacebookMessagingService(page_access_token=page_access_token)
