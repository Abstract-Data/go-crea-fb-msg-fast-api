"""Send messages to Facebook Graph API service."""

import time

import httpx
import logfire


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
        api_version="v18.0",
    )

    url = "https://graph.facebook.com/v18.0/me/messages"

    params = {"access_token": page_access_token}

    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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
