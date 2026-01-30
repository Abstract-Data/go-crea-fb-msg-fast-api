"""Facebook webhook endpoints."""

import logging
import random

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import PlainTextResponse

from src.config import get_settings
from src.db.repository import (
    get_bot_configuration_by_page_id,
    get_reference_document,
    get_user_profile,
    save_message_history,
    update_user_profile,
    upsert_user_profile,
)
from src.models.agent_models import AgentContext
from src.models.user_models import UserProfileCreate, UserProfileUpdate
from src.services.agent_service import MessengerAgentService
from src.services.facebook_service import get_user_info, send_message

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
            if not sender_id:
                continue

            message = messaging_event.get("message", {})
            message_text = message.get("text")

            if message_text:
                background_tasks.add_task(
                    process_message,
                    page_id=page_id,
                    sender_id=sender_id,
                    message_text=message_text,
                )

            # Location sharing (attachments with coordinates)
            attachments = message.get("attachments") or []
            location = attachments[0].get("payload") if attachments else None
            if location and location.get("coordinates"):
                background_tasks.add_task(
                    process_location,
                    page_id=page_id,
                    sender_id=sender_id,
                    location=location,
                )

    return {"status": "ok"}


async def process_message(page_id: str, sender_id: str, message_text: str):
    """Process incoming message and send response."""
    try:
        bot_config = get_bot_configuration_by_page_id(page_id)
        if not bot_config:
            logger.error("No bot configuration found for page_id: %s", page_id)
            return

        user_profile = get_user_profile(sender_id, page_id)
        if not user_profile:
            logger.info("New user %s, fetching profile from Facebook", sender_id)
            fb_user_info = await get_user_info(
                page_access_token=bot_config.facebook_page_access_token,
                user_id=sender_id,
            )
            if fb_user_info:
                new_profile = UserProfileCreate(
                    sender_id=sender_id,
                    page_id=page_id,
                    first_name=fb_user_info.first_name,
                    last_name=fb_user_info.last_name,
                    profile_pic=fb_user_info.profile_pic,
                    locale=fb_user_info.locale,
                    timezone=fb_user_info.timezone,
                )
                upsert_user_profile(new_profile)
                user_profile = get_user_profile(sender_id, page_id)

        ref_doc = get_reference_document(bot_config.reference_doc_id)
        if not ref_doc:
            logger.error("No reference document found: %s", bot_config.reference_doc_id)
            return

        recent_messages: list[str] = []
        user_name = user_profile.get("first_name") if user_profile else None
        user_location = user_profile.get("location_title") if user_profile else None

        context = AgentContext(
            bot_config_id=bot_config.id,
            reference_doc_id=bot_config.reference_doc_id,
            reference_doc=ref_doc["content"],
            tone=bot_config.tone,
            recent_messages=recent_messages,
            tenant_id=getattr(bot_config, "tenant_id", None),
            user_name=user_name,
            user_location=user_location,
        )

        agent_service = MessengerAgentService()
        response = await agent_service.respond(context, message_text)

        response_text = response.message
        if user_name and response.confidence > 0.8:
            if not response_text.startswith(user_name) and random.random() < 0.2:
                response_text = f"Hi {user_name}! {response_text}"

        await send_message(
            page_access_token=bot_config.facebook_page_access_token,
            recipient_id=sender_id,
            text=response_text,
        )

        save_message_history(
            bot_id=bot_config.id,
            sender_id=sender_id,
            message_text=message_text,
            response_text=response_text,
            confidence=response.confidence,
            requires_escalation=response.requires_escalation,
            user_profile_id=user_profile["id"] if user_profile else None,
        )

        logger.info(
            "Processed message for page %s: user_name=%s, location=%s, confidence=%s, escalation=%s",
            page_id,
            user_name or "unknown",
            user_location or "unknown",
            response.confidence,
            response.requires_escalation,
        )

    except Exception as e:
        logger.error("Error processing message: %s", e, exc_info=True)


async def process_location(
    page_id: str,
    sender_id: str,
    location: dict,
) -> None:
    """Process location shared by user via Messenger."""
    try:
        logger.info("Processing location for user %s", sender_id)
        coords = location.get("coordinates", {}) or {}
        lat = coords.get("lat")
        long_val = coords.get("long") or coords.get("lng")
        title = location.get("title")
        address = location.get("address")

        if not (lat is not None and long_val is not None):
            logger.warning("Invalid location data for user %s", sender_id)
            return

        updates = UserProfileUpdate(
            location_lat=float(lat),
            location_long=float(long_val),
            location_title=title,
            location_address=address,
        )
        success = update_user_profile(sender_id, page_id, updates)

        if success:
            logger.info(
                "Updated location for user %s: %s",
                sender_id,
                title or f"{lat},{long_val}",
            )
            bot_config = get_bot_configuration_by_page_id(page_id)
            if bot_config:
                place = title or "your area"
                await send_message(
                    page_access_token=bot_config.facebook_page_access_token,
                    recipient_id=sender_id,
                    text=f"Thanks for sharing your location! I see you're in {place}. How can I help you today?",
                )
    except Exception as e:
        logger.error("Error processing location: %s", e, exc_info=True)
