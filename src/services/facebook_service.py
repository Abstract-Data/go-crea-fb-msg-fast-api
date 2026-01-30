"""Send messages to Facebook Graph API service."""

import time
from typing import Any

import httpx
import logfire

from src.config import get_settings
from src.constants import FACEBOOK_GRAPH_API_VERSION
from src.models.user_models import FacebookUserInfo


def _parse_profile_pic(data: dict[str, Any]) -> str | None:
    """Extract profile picture URL from Graph API picture response."""
    pic = data.get("picture")
    if not isinstance(pic, dict):
        return None
    inner = pic.get("data")
    if not isinstance(inner, dict):
        return None
    url = inner.get("url")
    return str(url) if isinstance(url, str) else None


async def get_user_info(
    page_access_token: str,
    user_id: str,
) -> FacebookUserInfo | None:
    """
    Get basic user info from Facebook Graph API (no consent required).

    Fetches first_name, last_name, profile_pic, locale, timezone.
    """
    fields = [
        "first_name",
        "last_name",
        "picture.type(large)",
        "locale",
        "timezone",
    ]
    logfire.info(
        "Fetching basic user info from Facebook",
        user_id=user_id,
        fields=fields,
    )
    url = f"https://graph.facebook.com/{FACEBOOK_GRAPH_API_VERSION}/{user_id}"
    params = {
        "access_token": page_access_token,
        "fields": ",".join(fields),
    }
    try:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.facebook_api_timeout_seconds) as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                profile_pic = _parse_profile_pic(data)
                logfire.info(
                    "User info fetched successfully",
                    user_id=user_id,
                    has_name=bool(data.get("first_name")),
                    locale=data.get("locale"),
                )
                return FacebookUserInfo(
                    id=data.get("id", user_id),
                    first_name=data.get("first_name"),
                    last_name=data.get("last_name"),
                    profile_pic=profile_pic,
                    locale=data.get("locale"),
                    timezone=data.get("timezone"),
                )
            logfire.error(
                "Failed to fetch user info",
                user_id=user_id,
                status_code=response.status_code,
                response_body=response.text[:500],
            )
            return None
    except Exception as e:
        logfire.error(
            "Error fetching user info",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


async def send_message(
    page_access_token: str,
    recipient_id: str,
    text: str,
) -> None:
    """
    Send message via Facebook Graph API.

    Args:
        page_access_token: Facebook Page access token
        recipient_id: Facebook user ID to send message to
        text: Message text to send
    """
    start_time = time.time()

    logfire.info(
        "Sending Facebook message",
        recipient_id=recipient_id,
        message_length=len(text),
        api_version=FACEBOOK_GRAPH_API_VERSION,
    )

    url = f"https://graph.facebook.com/{FACEBOOK_GRAPH_API_VERSION}/me/messages"

    params = {"access_token": page_access_token}

    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}

    try:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.facebook_api_timeout_seconds) as client:
            response = await client.post(url, params=params, json=payload)
            elapsed = time.time() - start_time

            if response.status_code == 200:
                response_data = response.json()
                logfire.info(
                    "Facebook message sent successfully",
                    recipient_id=recipient_id,
                    status_code=response.status_code,
                    message_id=response_data.get("message_id"),
                    response_time_ms=elapsed * 1000,
                )
            else:
                logfire.error(
                    "Facebook message send failed",
                    recipient_id=recipient_id,
                    status_code=response.status_code,
                    response_body=response.text[:500],  # Limit response body length
                    response_time_ms=elapsed * 1000,
                )

            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Facebook API HTTP error",
            recipient_id=recipient_id,
            status_code=e.response.status_code if e.response else None,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
        )
        raise
    except httpx.RequestError as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Facebook API request error",
            recipient_id=recipient_id,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
        )
        raise
