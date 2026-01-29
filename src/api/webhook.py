"""Facebook webhook endpoints.

This module handles incoming Facebook Messenger webhooks with multiple
security layers and dependency injection support for testability.

Security layers (in order):
1. Rate limiting - prevents abuse from single users
2. Input validation - ensures message meets basic requirements
3. Prompt injection detection - blocks malicious manipulation attempts
4. Input sanitization - cleans input for safe processing

The webhook handlers focus on HTTP concerns and security validation,
delegating business logic to the MessageProcessor service.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import PlainTextResponse

from src.config import get_settings
from src.db.repository import (
    get_bot_configuration_by_page_id,
    update_user_profile,
)
from src.middleware.rate_limiter import RateLimiter, get_rate_limiter
from src.models.user_models import UserProfileUpdate
from src.services.facebook_service import send_message
from src.services.input_sanitizer import (
    get_user_friendly_error,
    sanitize_user_input,
    validate_message,
)
from src.services.message_processor import (
    BotConfigNotFoundError,
    MessageProcessor,
    ReferenceDocNotFoundError,
    get_message_processor,
)
from src.services.prompt_guard import PromptInjectionDetector, get_prompt_guard

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


async def process_message(
    page_id: str,
    sender_id: str,
    message_text: str,
    *,
    processor: MessageProcessor | None = None,
    rate_limiter: RateLimiter | None = None,
    prompt_guard: PromptInjectionDetector | None = None,
):
    """Process incoming message and send response.

    This function handles security validation and delegates business logic
    to the MessageProcessor service. Supports dependency injection for testing.

    Args:
        page_id: Facebook Page ID that received the message
        sender_id: Facebook user ID (PSID) who sent the message
        message_text: The message text content
        processor: Optional injected message processor (for testing)
        rate_limiter: Optional injected rate limiter (for testing)
        prompt_guard: Optional injected prompt guard (for testing)

    Security checks performed in order:
        1. Rate limiting - prevents abuse from single users
        2. Input validation - ensures message meets basic requirements
        3. Prompt injection detection - blocks malicious manipulation attempts
        4. Input sanitization - cleans input for safe processing
    """
    try:
        # ======================================================================
        # Security Layer 1: Rate Limiting
        # ======================================================================
        _rate_limiter = rate_limiter or get_rate_limiter()
        if not _rate_limiter.check_rate_limit(sender_id):
            logger.warning("Rate limit exceeded for user %s", sender_id)
            # Optionally send a polite rate limit message
            bot_config = get_bot_configuration_by_page_id(page_id)
            if bot_config:
                await send_message(
                    page_access_token=bot_config.facebook_page_access_token,
                    recipient_id=sender_id,
                    text="You're sending messages too quickly. Please wait a moment before sending another message.",
                )
            return

        # ======================================================================
        # Security Layer 2: Input Validation
        # ======================================================================
        validation_result = validate_message(message_text)
        if not validation_result.is_valid:
            logger.warning(
                "Invalid message from %s: %s",
                sender_id,
                validation_result.error_code,
            )
            # Send user-friendly error if appropriate
            error_msg = get_user_friendly_error(validation_result.error_code)
            if error_msg:
                bot_config = get_bot_configuration_by_page_id(page_id)
                if bot_config:
                    await send_message(
                        page_access_token=bot_config.facebook_page_access_token,
                        recipient_id=sender_id,
                        text=error_msg,
                    )
            return

        # ======================================================================
        # Security Layer 3: Prompt Injection Detection
        # ======================================================================
        _prompt_guard = prompt_guard or get_prompt_guard()
        injection_result = _prompt_guard.check(message_text)

        if injection_result.is_suspicious and injection_result.risk_level == "high":
            logger.warning(
                "Blocked high-risk prompt injection from %s: %s",
                sender_id,
                injection_result.matched_pattern,
            )
            # Don't process, but don't reveal why to avoid helping attackers
            return

        # Log medium-risk patterns but allow processing
        if injection_result.is_suspicious and injection_result.risk_level == "medium":
            logger.info(
                "Medium-risk pattern detected from %s: %s (proceeding)",
                sender_id,
                injection_result.matched_pattern,
            )

        # ======================================================================
        # Security Layer 4: Input Sanitization
        # ======================================================================
        sanitized_message = sanitize_user_input(message_text)

        # ======================================================================
        # Main Processing - Delegate to MessageProcessor
        # ======================================================================
        _processor = processor or get_message_processor()

        try:
            await _processor.process(page_id, sender_id, sanitized_message)
        except BotConfigNotFoundError:
            logger.error("No bot configuration found for page_id: %s", page_id)
        except ReferenceDocNotFoundError as e:
            logger.error("Reference document not found: %s", e)

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
