"""Bot configuration and message history repository."""

import time
from datetime import datetime
from typing import Optional
import uuid

import logfire

from src.db.client import get_supabase_client
from src.models.config_models import BotConfiguration
from src.models.user_models import UserProfileCreate, UserProfileUpdate


def create_reference_document(
    content: str,
    source_url: str,
    content_hash: str,
) -> str:
    """
    Create a reference document (without bot_id initially).

    Args:
        content: Markdown content
        source_url: Source website URL
        content_hash: SHA256 hash of content

    Returns:
        Reference document ID
    """
    start_time = time.time()

    logfire.info(
        "Creating reference document",
        source_url=source_url,
        content_length=len(content),
        content_hash=content_hash,
    )

    supabase = get_supabase_client()

    data = {"content": content, "source_url": source_url, "content_hash": content_hash}

    try:
        result = supabase.table("reference_documents").insert(data).execute()
        elapsed = time.time() - start_time

        if not result.data:
            logfire.error(
                "Failed to create reference document",
                source_url=source_url,
                content_hash=content_hash,
                response_time_ms=elapsed * 1000,
            )
            raise ValueError("Failed to create reference document")

        doc_id = result.data[0]["id"]
        logfire.info(
            "Reference document created",
            document_id=doc_id,
            source_url=source_url,
            content_hash=content_hash,
            response_time_ms=elapsed * 1000,
        )
        return doc_id
    except Exception as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Error creating reference document",
            source_url=source_url,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
        )
        raise


def link_reference_document_to_bot(doc_id: str, bot_id: str) -> None:
    """Link reference document to bot configuration."""
    supabase = get_supabase_client()

    supabase.table("reference_documents").update({"bot_id": bot_id}).eq(
        "id", doc_id
    ).execute()


def create_bot_configuration(
    page_id: str,
    website_url: str,
    reference_doc_id: str,
    tone: str,
    facebook_page_access_token: str,
    facebook_verify_token: str,
) -> BotConfiguration:
    """
    Create a new bot configuration.

    Args:
        page_id: Facebook Page ID
        website_url: Source website URL
        reference_doc_id: Reference document UUID
        tone: Communication tone
        facebook_page_access_token: Page access token
        facebook_verify_token: Webhook verify token

    Returns:
        Created BotConfiguration
    """
    supabase = get_supabase_client()

    now = datetime.utcnow()
    bot_id = str(uuid.uuid4())

    data = {
        "id": bot_id,
        "page_id": page_id,
        "website_url": website_url,
        "reference_doc_id": reference_doc_id,
        "tone": tone,
        "facebook_page_access_token": facebook_page_access_token,
        "facebook_verify_token": facebook_verify_token,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "is_active": True,
    }

    result = supabase.table("bot_configurations").insert(data).execute()

    if not result.data:
        raise ValueError("Failed to create bot configuration")

    # Link reference document to bot
    link_reference_document_to_bot(reference_doc_id, bot_id)

    return BotConfiguration(**result.data[0])


def get_bot_configuration_by_page_id(page_id: str) -> Optional[BotConfiguration]:
    """
    Get bot configuration by Facebook Page ID.

    Returns:
        BotConfiguration if found, None otherwise
    """
    start_time = time.time()

    logfire.info(
        "Fetching bot configuration",
        page_id=page_id,
    )

    supabase = get_supabase_client()

    try:
        result = (
            supabase.table("bot_configurations")
            .select("*")
            .eq("page_id", page_id)
            .eq("is_active", True)
            .execute()
        )
        elapsed = time.time() - start_time

        if not result.data:
            logfire.info(
                "Bot configuration not found",
                page_id=page_id,
                response_time_ms=elapsed * 1000,
            )
            return None

        logfire.info(
            "Bot configuration fetched",
            page_id=page_id,
            bot_id=result.data[0].get("id"),
            response_time_ms=elapsed * 1000,
        )
        return BotConfiguration(**result.data[0])
    except Exception as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Error fetching bot configuration",
            page_id=page_id,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
        )
        raise


def get_reference_document(doc_id: str) -> Optional[dict]:
    """
    Get reference document by ID.

    Returns:
        Document dict with 'content' and other fields, or None
    """
    supabase = get_supabase_client()

    result = (
        supabase.table("reference_documents").select("*").eq("id", doc_id).execute()
    )

    if not result.data:
        return None

    return result.data[0]


def get_reference_document_by_source_url(source_url: str) -> Optional[dict]:
    """
    Get the most recent reference document for a given source URL.
    Used to resume setup: if we already scraped and saved a doc for this URL,
    we skip scrape/build and proceed to tone and Facebook config.

    Returns:
        Document dict with 'id', 'content_hash', etc., or None
    """
    if not source_url or not source_url.strip():
        return None
    supabase = get_supabase_client()
    result = (
        supabase.table("reference_documents")
        .select("*")
        .eq("source_url", source_url.strip())
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]


def get_user_profile(sender_id: str, page_id: str) -> dict | None:
    """
    Get user profile by sender_id (unique per user).

    page_id is accepted for API consistency but lookup is by sender_id only.

    Returns:
        User profile dict or None if not found
    """
    try:
        client = get_supabase_client()
        result = (
            client.table("user_profiles")
            .select("*")
            .eq("sender_id", sender_id)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logfire.error(
            "Error getting user profile",
            sender_id=sender_id,
            page_id=page_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


def create_user_profile(profile: UserProfileCreate) -> str | None:
    """
    Create a new user profile.

    Returns:
        User profile ID or None on error
    """
    try:
        client = get_supabase_client()
        data = profile.model_dump(exclude_none=True)
        result = client.table("user_profiles").insert(data).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]["id"]
        return None
    except Exception as e:
        logfire.error(
            "Error creating user profile",
            sender_id=profile.sender_id,
            page_id=profile.page_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


def update_user_profile(
    sender_id: str,
    page_id: str,
    updates: UserProfileUpdate,
) -> bool:
    """
    Update user profile (by sender_id).

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_supabase_client()
        update_data = updates.model_dump(exclude_none=True)
        if not update_data:
            return True
        result = (
            client.table("user_profiles")
            .update(update_data)
            .eq("sender_id", sender_id)
            .execute()
        )
        return result.data is not None and len(result.data) > 0
    except Exception as e:
        logfire.error(
            "Error updating user profile",
            sender_id=sender_id,
            page_id=page_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


def upsert_user_profile(profile: UserProfileCreate) -> str | None:
    """
    Create or update user profile (upsert on sender_id).

    Returns:
        User profile ID or None on error
    """
    try:
        client = get_supabase_client()
        data = profile.model_dump(exclude_none=True)
        result = (
            client.table("user_profiles")
            .upsert(data, on_conflict="sender_id")
            .execute()
        )
        if result.data and len(result.data) > 0:
            return result.data[0]["id"]
        return None
    except Exception as e:
        logfire.error(
            "Error upserting user profile",
            sender_id=profile.sender_id,
            page_id=profile.page_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


def save_message_history(
    bot_id: str,
    sender_id: str,
    message_text: str,
    response_text: str,
    confidence: float,
    requires_escalation: bool = False,
    user_profile_id: str | None = None,
) -> None:
    """Save message to history."""
    start_time = time.time()

    logfire.info(
        "Saving message history",
        bot_id=bot_id,
        sender_id=sender_id,
        message_length=len(message_text),
        response_length=len(response_text),
        confidence=confidence,
        requires_escalation=requires_escalation,
        user_profile_id=user_profile_id,
    )

    supabase = get_supabase_client()

    data = {
        "bot_id": bot_id,
        "sender_id": sender_id,
        "message_text": message_text,
        "response_text": response_text,
        "confidence": confidence,
        "requires_escalation": requires_escalation,
        "created_at": datetime.utcnow().isoformat(),
    }
    if user_profile_id is not None:
        data["user_profile_id"] = user_profile_id

    try:
        result = supabase.table("message_history").insert(data).execute()
        elapsed = time.time() - start_time

        logfire.info(
            "Message history saved",
            bot_id=bot_id,
            sender_id=sender_id,
            message_id=result.data[0].get("id") if result.data else None,
            response_time_ms=elapsed * 1000,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Error saving message history",
            bot_id=bot_id,
            sender_id=sender_id,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
        )
        raise


def create_test_session(reference_doc_id: str, source_url: str, tone: str) -> str:
    """
    Create a test session for REPL persistence.

    Args:
        reference_doc_id: Reference document UUID
        source_url: Source website URL
        tone: Communication tone

    Returns:
        Test session ID
    """
    start_time = time.time()

    logfire.info(
        "Creating test session",
        reference_doc_id=reference_doc_id,
        source_url=source_url,
        tone=tone,
    )

    supabase = get_supabase_client()

    data = {
        "reference_doc_id": reference_doc_id,
        "source_url": source_url,
        "tone": tone,
    }

    try:
        result = supabase.table("test_sessions").insert(data).execute()
        elapsed = time.time() - start_time

        if not result.data:
            logfire.error(
                "Failed to create test session",
                reference_doc_id=reference_doc_id,
                source_url=source_url,
                response_time_ms=elapsed * 1000,
            )
            raise ValueError("Failed to create test session")

        session_id = result.data[0]["id"]
        logfire.info(
            "Test session created",
            session_id=session_id,
            reference_doc_id=reference_doc_id,
            response_time_ms=elapsed * 1000,
        )
        return session_id
    except Exception as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Error creating test session",
            reference_doc_id=reference_doc_id,
            source_url=source_url,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
        )
        raise


def save_test_message(
    test_session_id: str,
    user_message: str,
    response_text: str,
    confidence: float,
    requires_escalation: bool = False,
    escalation_reason: str | None = None,
) -> None:
    """
    Save a test REPL exchange to history. Does not raise on Supabase errors.
    """
    start_time = time.time()

    logfire.info(
        "Saving test message",
        test_session_id=test_session_id,
        message_length=len(user_message),
        response_length=len(response_text),
        confidence=confidence,
        requires_escalation=requires_escalation,
    )

    supabase = get_supabase_client()

    data = {
        "test_session_id": test_session_id,
        "user_message": user_message,
        "response_text": response_text,
        "confidence": confidence,
        "requires_escalation": requires_escalation,
        "escalation_reason": escalation_reason,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        result = supabase.table("test_messages").insert(data).execute()
        elapsed = time.time() - start_time

        logfire.info(
            "Test message saved",
            test_session_id=test_session_id,
            message_id=result.data[0].get("id") if result.data else None,
            response_time_ms=elapsed * 1000,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Error saving test message",
            test_session_id=test_session_id,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
        )
