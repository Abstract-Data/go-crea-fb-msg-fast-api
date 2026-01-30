"""Application-wide constants.

This module centralizes all magic numbers and configuration constants
to ensure a single source of truth and easier maintenance.

Constants are organized by category and include references to their
source (GUARDRAILS.md, etc.) where applicable.
"""

# =============================================================================
# Scraping Configuration
# =============================================================================

# Target word count per chunk when splitting scraped content
DEFAULT_CHUNK_SIZE_WORDS = 650

# Minimum word count to consider a page as properly rendered
# Below this threshold, the scraper will retry with browser rendering
MIN_JS_RENDERED_PAGE_WORDS = 400

# Delay between HTTP requests to be polite to target servers (seconds)
POLITE_REQUEST_DELAY_SECONDS = 0.5

# Maximum number of pages to scrape from a website
DEFAULT_MAX_SCRAPE_PAGES = 20

# Maximum reference document size (from GUARDRAILS.md)
MAX_REFERENCE_DOC_CHARS = 50000

# =============================================================================
# HTTP Timeout Configuration
# =============================================================================

# Default timeout for scraper HTTP requests (seconds)
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0

# Timeout for Facebook Graph API calls (seconds)
FACEBOOK_API_TIMEOUT_SECONDS = 10.0

# Timeout for browser page loads, e.g., undetected Chrome (seconds)
BROWSER_PAGE_LOAD_TIMEOUT_SECONDS = 30.0

# Extended timeout for JS-rendered pages that need browser refetch (seconds)
BROWSER_JS_REFETCH_TIMEOUT_SECONDS = 45.0

# =============================================================================
# Message Constraints (from GUARDRAILS.md)
# =============================================================================

# Maximum allowed input message length (chars)
# Facebook Messenger limit is 2000, but we enforce stricter limit
MAX_MESSAGE_LENGTH_CHARS = 1000

# Maximum agent response length (chars) - Facebook Messenger best practice
MAX_RESPONSE_LENGTH_CHARS = 300

# =============================================================================
# Rate Limiting (from GUARDRAILS.md)
# =============================================================================

# Maximum messages per user per minute
MAX_MESSAGES_PER_USER_PER_MINUTE = 10

# Rate limit window in seconds
RATE_LIMIT_WINDOW_SECONDS = 60

# =============================================================================
# RAG / Search Configuration
# =============================================================================

# Default number of chunks to return from semantic search
DEFAULT_SEARCH_RESULT_LIMIT = 5

# Content preview length for search results (chars)
SEARCH_RESULT_CONTENT_PREVIEW_CHARS = 500

# =============================================================================
# Embedding Configuration
# =============================================================================

# Default embedding vector dimension (matches text-embedding-3-small)
DEFAULT_EMBEDDING_DIMENSIONS = 1536

# =============================================================================
# Agent Configuration
# =============================================================================

# Number of retries for agent calls
AGENT_RETRY_COUNT = 2

# Number of recent messages to include in context
AGENT_RECENT_MESSAGES_COUNT = 6

# Confidence threshold below which to escalate (from GUARDRAILS.md)
ESCALATION_CONFIDENCE_THRESHOLD = 0.7

# Maximum retries for same message before escalation (from GUARDRAILS.md)
MAX_MESSAGE_RETRIES = 3

# =============================================================================
# Personalization Configuration
# =============================================================================

# Confidence threshold above which to personalize responses
PERSONALIZATION_CONFIDENCE_THRESHOLD = 0.8

# Probability of adding a greeting with user's name
PERSONALIZATION_GREETING_PROBABILITY = 0.2

# =============================================================================
# Cache Configuration
# =============================================================================

# TTL for bot configuration cache (seconds) - 5 minutes
BOT_CONFIG_CACHE_TTL_SECONDS = 300

# =============================================================================
# Data Retention (from GUARDRAILS.md)
# =============================================================================

# Message history retention period (days)
MESSAGE_HISTORY_RETENTION_DAYS = 90

# =============================================================================
# Facebook API
# =============================================================================

# Facebook Graph API version
FACEBOOK_GRAPH_API_VERSION = "v18.0"
