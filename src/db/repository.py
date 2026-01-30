"""Bot configuration and message history repository."""

import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, List, Optional
import uuid

import logfire

from src.constants import BOT_CONFIG_CACHE_TTL_SECONDS
from src.db.client import get_supabase_client
from src.models.config_models import BotConfiguration, BotConfigurationCreate
from src.models.message_models import MessageHistoryCreate, TestMessageCreate
from src.models.scraper_models import ScrapedPageCreate
from src.models.user_models import UserProfileCreate, UserProfileUpdate


# =============================================================================
# Bot Configuration Cache
# =============================================================================


class BotConfigCache:
    """
    Thread-safe in-memory cache for bot configurations.

    Caches bot configurations by page_id with configurable TTL to reduce
    database queries on every incoming message. The cache is thread-safe
    and automatically expires entries after the TTL.
    """

    def __init__(self, ttl_seconds: int = BOT_CONFIG_CACHE_TTL_SECONDS):
        """
        Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default: 300)
        """
        self._cache: dict[str, tuple[BotConfiguration, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = Lock()

    def get(self, page_id: str) -> BotConfiguration | None:
        """
        Get cached configuration if not expired.

        Args:
            page_id: Facebook Page ID

        Returns:
            Cached BotConfiguration if valid, None if not found or expired
        """
        with self._lock:
            if page_id in self._cache:
                config, timestamp = self._cache[page_id]
                if datetime.utcnow() - timestamp < self._ttl:
                    logfire.debug(
                        "Bot config cache hit",
                        page_id=page_id,
                        cache_age_seconds=(
                            datetime.utcnow() - timestamp
                        ).total_seconds(),
                    )
                    return config
                # Expired - remove from cache
                del self._cache[page_id]
                logfire.debug(
                    "Bot config cache expired",
                    page_id=page_id,
                )
            return None

    def set(self, page_id: str, config: BotConfiguration) -> None:
        """
        Cache a configuration.

        Args:
            page_id: Facebook Page ID
            config: Bot configuration to cache
        """
        with self._lock:
            self._cache[page_id] = (config, datetime.utcnow())
            logfire.debug(
                "Bot config cached",
                page_id=page_id,
                bot_id=config.id,
            )

    def invalidate(self, page_id: str) -> None:
        """
        Remove configuration from cache.

        Args:
            page_id: Facebook Page ID to invalidate
        """
        with self._lock:
            if page_id in self._cache:
                del self._cache[page_id]
                logfire.debug(
                    "Bot config cache invalidated",
                    page_id=page_id,
                )

    def clear(self) -> None:
        """Clear all cached configurations."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logfire.debug(
                "Bot config cache cleared",
                entries_cleared=count,
            )

    @property
    def size(self) -> int:
        """Get number of cached entries."""
        with self._lock:
            return len(self._cache)


# Global cache instance
_bot_config_cache: BotConfigCache | None = None


def get_bot_config_cache() -> BotConfigCache:
    """Get or create the global bot config cache instance."""
    global _bot_config_cache
    if _bot_config_cache is None:
        _bot_config_cache = BotConfigCache()
    return _bot_config_cache


def reset_bot_config_cache() -> None:
    """Reset the global cache (primarily for testing)."""
    global _bot_config_cache
    if _bot_config_cache is not None:
        _bot_config_cache.clear()
    _bot_config_cache = None


# =============================================================================
# Reference Documents
# =============================================================================


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
    config: BotConfigurationCreate | None = None,
    *,
    # Legacy parameters for backward compatibility
    page_id: str | None = None,
    website_url: str | None = None,
    reference_doc_id: str | None = None,
    tone: str | None = None,
    facebook_page_access_token: str | None = None,
    facebook_verify_token: str | None = None,
) -> BotConfiguration:
    """
    Create a new bot configuration.

    Args:
        config: BotConfigurationCreate parameter object (preferred)

        Legacy parameters (deprecated, use config instead):
        page_id: Facebook Page ID
        website_url: Source website URL
        reference_doc_id: Reference document UUID
        tone: Communication tone
        facebook_page_access_token: Page access token
        facebook_verify_token: Webhook verify token

    Returns:
        Created BotConfiguration
    """
    # Support both parameter object and legacy parameters
    if config is not None:
        _page_id = config.page_id
        _website_url = config.website_url
        _reference_doc_id = config.reference_doc_id
        _tone = config.tone
        _facebook_page_access_token = config.facebook_page_access_token
        _facebook_verify_token = config.facebook_verify_token
    else:
        # Legacy parameter validation
        if not all(
            [
                page_id,
                website_url,
                reference_doc_id,
                tone,
                facebook_page_access_token,
                facebook_verify_token,
            ]
        ):
            raise ValueError(
                "Either provide a BotConfigurationCreate object or all legacy parameters"
            )
        _page_id = page_id  # type: ignore[assignment]
        _website_url = website_url  # type: ignore[assignment]
        _reference_doc_id = reference_doc_id  # type: ignore[assignment]
        _tone = tone  # type: ignore[assignment]
        _facebook_page_access_token = facebook_page_access_token  # type: ignore[assignment]
        _facebook_verify_token = facebook_verify_token  # type: ignore[assignment]

    supabase = get_supabase_client()

    now = datetime.utcnow()
    bot_id = str(uuid.uuid4())

    data = {
        "id": bot_id,
        "page_id": _page_id,
        "website_url": _website_url,
        "reference_doc_id": _reference_doc_id,
        "tone": _tone,
        "facebook_page_access_token": _facebook_page_access_token,
        "facebook_verify_token": _facebook_verify_token,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "is_active": True,
    }

    result = supabase.table("bot_configurations").insert(data).execute()

    if not result.data:
        raise ValueError("Failed to create bot configuration")

    # Link reference document to bot
    link_reference_document_to_bot(_reference_doc_id, bot_id)

    # Invalidate cache for this page_id to ensure fresh config is fetched
    cache = get_bot_config_cache()
    cache.invalidate(_page_id)

    return BotConfiguration(**result.data[0])


def get_bot_configuration_by_page_id(page_id: str) -> Optional[BotConfiguration]:
    """
    Get bot configuration by Facebook Page ID.

    Uses an in-memory cache to reduce database queries on every message.
    Cache entries expire after BOT_CONFIG_CACHE_TTL_SECONDS (default: 5 minutes).

    Returns:
        BotConfiguration if found, None otherwise
    """
    # Check cache first
    cache = get_bot_config_cache()
    cached = cache.get(page_id)
    if cached is not None:
        return cached

    start_time = time.time()

    logfire.info(
        "Fetching bot configuration from database",
        page_id=page_id,
        cache_status="miss",
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

        config = BotConfiguration(**result.data[0])

        # Cache the result
        cache.set(page_id, config)

        logfire.info(
            "Bot configuration fetched and cached",
            page_id=page_id,
            bot_id=config.id,
            response_time_ms=elapsed * 1000,
        )
        return config
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


def _embedding_to_text(embedding: List[float]) -> str:
    """Format embedding list as pgvector text literal '[a,b,c,...]'."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def create_scraped_page(
    page: ScrapedPageCreate | None = None,
    *,
    # Legacy parameters for backward compatibility
    reference_doc_id: str | None = None,
    url: str | None = None,
    normalized_url: str | None = None,
    title: str | None = None,
    raw_content: str | None = None,
    word_count: int | None = None,
    scraped_at: datetime | None = None,
) -> str:
    """
    Insert a single scraped page row.

    Args:
        page: ScrapedPageCreate parameter object (preferred)

        Legacy parameters (deprecated, use page instead):
        reference_doc_id: Reference document UUID
        url: Original page URL
        normalized_url: Normalized URL for deduplication
        title: Page title
        raw_content: Scraped text content
        word_count: Word count
        scraped_at: Scrape timestamp

    Returns:
        scraped_page id (uuid string)
    """
    # Support both parameter object and legacy parameters
    if page is not None:
        _reference_doc_id = page.reference_doc_id
        _url = page.url
        _normalized_url = page.normalized_url
        _title = page.title
        _raw_content = page.raw_content
        _word_count = page.word_count
        _scraped_at = page.scraped_at
    else:
        # Legacy parameter validation
        if not all(
            [
                reference_doc_id,
                url,
                normalized_url,
                raw_content is not None,
                word_count is not None,
                scraped_at,
            ]
        ):
            raise ValueError(
                "Either provide a ScrapedPageCreate object or all legacy parameters"
            )
        _reference_doc_id = reference_doc_id  # type: ignore[assignment]
        _url = url  # type: ignore[assignment]
        _normalized_url = normalized_url  # type: ignore[assignment]
        _title = title or ""
        _raw_content = raw_content  # type: ignore[assignment]
        _word_count = word_count  # type: ignore[assignment]
        _scraped_at = scraped_at  # type: ignore[assignment]

    supabase = get_supabase_client()
    data = {
        "reference_doc_id": _reference_doc_id,
        "url": _url,
        "normalized_url": _normalized_url,
        "title": _title or "",
        "raw_content": _raw_content,
        "word_count": _word_count,
        "scraped_at": _scraped_at.isoformat()
        if hasattr(_scraped_at, "isoformat")
        else _scraped_at,
    }
    result = supabase.table("scraped_pages").insert(data).execute()
    if not result.data:
        raise ValueError("Failed to create scraped_page")
    return result.data[0]["id"]


def create_page_chunks(
    scraped_page_id: str,
    chunks_with_embeddings: List[tuple[str, List[float], int]],
) -> None:
    """
    Batch insert page chunks with embeddings.

    chunks_with_embeddings: list of (content, embedding, word_count) per chunk.
    """
    if not chunks_with_embeddings:
        return
    supabase = get_supabase_client()
    rows: List[dict[str, Any]] = []
    for idx, (content, embedding, word_count) in enumerate(chunks_with_embeddings):
        rows.append(
            {
                "scraped_page_id": scraped_page_id,
                "chunk_index": idx,
                "content": content,
                "embedding": embedding,  # Supabase accepts list for vector column
                "word_count": word_count,
            }
        )
    supabase.table("page_chunks").insert(rows).execute()
    logfire.info(
        "Page chunks created",
        scraped_page_id=scraped_page_id,
        chunk_count=len(rows),
    )


def search_page_chunks(
    query_embedding: List[float],
    reference_doc_id: str,
    limit: int = 5,
) -> List[dict[str, Any]]:
    """
    Semantic search over page chunks for a given reference document.

    Returns list of dicts with id, scraped_page_id, chunk_index, content, word_count, page_url, distance.
    """
    supabase = get_supabase_client()
    query_embedding_text = _embedding_to_text(query_embedding)
    result = supabase.rpc(
        "search_page_chunks",
        {
            "query_embedding_text": query_embedding_text,
            "ref_doc_id": reference_doc_id,
            "match_limit": limit,
        },
    ).execute()
    if not result.data:
        return []
    return list(result.data)


def get_scraped_pages_by_reference_doc(reference_doc_id: str) -> List[dict[str, Any]]:
    """List all scraped pages for a reference document."""
    supabase = get_supabase_client()
    result = (
        supabase.table("scraped_pages")
        .select("*")
        .eq("reference_doc_id", reference_doc_id)
        .order("created_at")
        .execute()
    )
    return list(result.data) if result.data else []


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


def upsert_user_profile(profile: UserProfileCreate) -> dict | None:
    """
    Create or update user profile (upsert on sender_id).

    Returns the full profile dict on success, eliminating the need for a
    follow-up query to fetch the profile after upsert.

    Returns:
        Full user profile dict or None on error
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
            return result.data[0]  # Return full profile, not just ID
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
    message: MessageHistoryCreate | None = None,
    *,
    # Legacy parameters for backward compatibility
    bot_id: str | None = None,
    sender_id: str | None = None,
    message_text: str | None = None,
    response_text: str | None = None,
    confidence: float | None = None,
    requires_escalation: bool = False,
    user_profile_id: str | None = None,
) -> None:
    """Save message to history.

    Args:
        message: MessageHistoryCreate parameter object (preferred)

        Legacy parameters (deprecated, use message instead):
        bot_id: Bot configuration ID
        sender_id: Facebook user ID
        message_text: User's incoming message
        response_text: Bot's response
        confidence: Response confidence score
        requires_escalation: Whether escalation needed
        user_profile_id: Associated user profile ID
    """
    # Support both parameter object and legacy parameters
    if message is not None:
        _bot_id = message.bot_id
        _sender_id = message.sender_id
        _message_text = message.message_text
        _response_text = message.response_text
        _confidence = message.confidence
        _requires_escalation = message.requires_escalation
        _user_profile_id = message.user_profile_id
    else:
        # Legacy parameter validation
        if not all(
            [
                bot_id,
                sender_id,
                message_text is not None,
                response_text is not None,
                confidence is not None,
            ]
        ):
            raise ValueError(
                "Either provide a MessageHistoryCreate object or all required legacy parameters"
            )
        _bot_id = bot_id  # type: ignore[assignment]
        _sender_id = sender_id  # type: ignore[assignment]
        _message_text = message_text  # type: ignore[assignment]
        _response_text = response_text  # type: ignore[assignment]
        _confidence = confidence  # type: ignore[assignment]
        _requires_escalation = requires_escalation
        _user_profile_id = user_profile_id

    start_time = time.time()

    logfire.info(
        "Saving message history",
        bot_id=_bot_id,
        sender_id=_sender_id,
        message_length=len(_message_text),
        response_length=len(_response_text),
        confidence=_confidence,
        requires_escalation=_requires_escalation,
        user_profile_id=_user_profile_id,
    )

    supabase = get_supabase_client()

    data = {
        "bot_id": _bot_id,
        "sender_id": _sender_id,
        "message_text": _message_text,
        "response_text": _response_text,
        "confidence": _confidence,
        "requires_escalation": _requires_escalation,
        "created_at": datetime.utcnow().isoformat(),
    }
    if _user_profile_id is not None:
        data["user_profile_id"] = _user_profile_id

    try:
        result = supabase.table("message_history").insert(data).execute()
        elapsed = time.time() - start_time

        logfire.info(
            "Message history saved",
            bot_id=_bot_id,
            sender_id=_sender_id,
            message_id=result.data[0].get("id") if result.data else None,
            response_time_ms=elapsed * 1000,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Error saving message history",
            bot_id=_bot_id,
            sender_id=_sender_id,
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
    message: TestMessageCreate | None = None,
    *,
    # Legacy parameters for backward compatibility
    test_session_id: str | None = None,
    user_message: str | None = None,
    response_text: str | None = None,
    confidence: float | None = None,
    requires_escalation: bool = False,
    escalation_reason: str | None = None,
) -> None:
    """
    Save a test REPL exchange to history. Does not raise on Supabase errors.

    Args:
        message: TestMessageCreate parameter object (preferred)

        Legacy parameters (deprecated, use message instead):
        test_session_id: Test session UUID
        user_message: User's test message
        response_text: Bot's response
        confidence: Response confidence score
        requires_escalation: Whether escalation needed
        escalation_reason: Reason for escalation
    """
    # Support both parameter object and legacy parameters
    if message is not None:
        _test_session_id = message.test_session_id
        _user_message = message.user_message
        _response_text = message.response_text
        _confidence = message.confidence
        _requires_escalation = message.requires_escalation
        _escalation_reason = message.escalation_reason
    else:
        # Legacy parameter validation
        if not all(
            [
                test_session_id,
                user_message is not None,
                response_text is not None,
                confidence is not None,
            ]
        ):
            raise ValueError(
                "Either provide a TestMessageCreate object or all required legacy parameters"
            )
        _test_session_id = test_session_id  # type: ignore[assignment]
        _user_message = user_message  # type: ignore[assignment]
        _response_text = response_text  # type: ignore[assignment]
        _confidence = confidence  # type: ignore[assignment]
        _requires_escalation = requires_escalation
        _escalation_reason = escalation_reason

    start_time = time.time()

    logfire.info(
        "Saving test message",
        test_session_id=_test_session_id,
        message_length=len(_user_message),
        response_length=len(_response_text),
        confidence=_confidence,
        requires_escalation=_requires_escalation,
    )

    supabase = get_supabase_client()

    data = {
        "test_session_id": _test_session_id,
        "user_message": _user_message,
        "response_text": _response_text,
        "confidence": _confidence,
        "requires_escalation": _requires_escalation,
        "escalation_reason": _escalation_reason,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        result = supabase.table("test_messages").insert(data).execute()
        elapsed = time.time() - start_time

        logfire.info(
            "Test message saved",
            test_session_id=_test_session_id,
            message_id=result.data[0].get("id") if result.data else None,
            response_time_ms=elapsed * 1000,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logfire.error(
            "Error saving test message",
            test_session_id=_test_session_id,
            error=str(e),
            error_type=type(e).__name__,
            response_time_ms=elapsed * 1000,
        )
