"""Facebook webhook endpoints."""

import logging
from fastapi import APIRouter, Request, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse

from src.config import get_settings
from src.db.repository import (
    get_bot_configuration_by_page_id,
    get_reference_document,
    save_message_history,
)
from src.models.agent_models import AgentContext
from src.services.agent_service import MessengerAgentService
from src.services.facebook_service import send_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def verify_webhook(request: Request):
    """Facebook webhook verification endpoint."""
    settings = get_settings()

    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.facebook_verify_token:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(challenge)

    logger.warning("Webhook verification failed")
    return Response(status_code=403)


@router.post("")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming Facebook Messenger webhook events."""
    payload = await request.json()

    if payload.get("object") != "page":
        return {"status": "ignored"}

    for entry in payload.get("entry", []):
        page_id = entry.get("id")

        for messaging_event in entry.get("messaging", []):
            sender_id = messaging_event.get("sender", {}).get("id")
            message = messaging_event.get("message", {})
            message_text = message.get("text")

            if not message_text:
                continue

            # Process message in background
            background_tasks.add_task(
                process_message,
                page_id=page_id,
                sender_id=sender_id,
                message_text=message_text,
            )

    return {"status": "ok"}


async def process_message(page_id: str, sender_id: str, message_text: str):
    """Process incoming message and send response."""
    try:
        # Get bot configuration
        bot_config = get_bot_configuration_by_page_id(page_id)
        if not bot_config:
            logger.error(f"No bot configuration found for page_id: {page_id}")
            return

        # Get reference document
        ref_doc = get_reference_document(bot_config.reference_doc_id)
        if not ref_doc:
            logger.error(f"No reference document found: {bot_config.reference_doc_id}")
            return

        # Build agent context
        context = AgentContext(
            bot_config_id=bot_config.id,
            reference_doc=ref_doc["content"],
            tone=bot_config.tone,
            recent_messages=[],  # TODO: Load from message_history
            tenant_id=getattr(bot_config, "tenant_id", None),
        )

        # Get response from agent (NEW: Using PydanticAI Gateway)
        agent_service = MessengerAgentService()
        response = await agent_service.respond(context, message_text)

        # Send response via Facebook
        await send_message(
            page_access_token=bot_config.facebook_page_access_token,
            recipient_id=sender_id,
            text=response.message,
        )

        # Save to history
        save_message_history(
            bot_id=bot_config.id,
            sender_id=sender_id,
            message_text=message_text,
            response_text=response.message,
            confidence=response.confidence,
            requires_escalation=response.requires_escalation,
        )

        logger.info(
            f"Processed message for page {page_id}: "
            f"confidence={response.confidence}, escalation={response.requires_escalation}"
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")
