"""Facebook webhook endpoints."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from src.config import get_settings

router = APIRouter()


@router.get("")
async def verify_webhook(request: Request):
    """
    Facebook webhook verification endpoint.
    
    Facebook sends a GET request with:
    - hub.mode: "subscribe"
    - hub.verify_token: The token you set
    - hub.challenge: A random string
    
    Returns the challenge if verify_token matches.
    """
    settings = get_settings()
    
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == settings.facebook_verify_token:
        return PlainTextResponse(challenge)
    
    return Response(status_code=403)


@router.post("")
async def handle_webhook(request: Request):
    """
    Facebook webhook message handler.
    
    Processes incoming Messenger messages and responds via agent.
    """
    # TODO: Implement message handling
    # 1. Parse webhook payload
    # 2. Extract message text and sender
    # 3. Look up bot configuration by page_id
    # 4. Build AgentContext
    # 5. Call MessengerAgentService.respond
    # 6. Send reply via Facebook Graph API
    
    return {"status": "ok"}
