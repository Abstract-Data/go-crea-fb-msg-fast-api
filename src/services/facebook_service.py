"""Send messages to Facebook Graph API service."""

import httpx


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
    url = "https://graph.facebook.com/v18.0/me/messages"
    
    params = {"access_token": page_access_token}
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, params=params, json=payload)
        response.raise_for_status()
