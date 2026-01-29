"""Website scraping and chunking service."""

import asyncio
import hashlib
import os
import re
import time
from datetime import datetime, timezone
from typing import List
from urllib.parse import urljoin, urlparse

import httpx
import logfire
from bs4 import BeautifulSoup

from src.config import get_settings
from src.constants import (
    DEFAULT_CHUNK_SIZE_WORDS,
    DEFAULT_MAX_SCRAPE_PAGES,
    MIN_JS_RENDERED_PAGE_WORDS,
    POLITE_REQUEST_DELAY_SECONDS,
)
from src.models.scraper_models import ScrapedPage, ScrapeResult


def chunk_text(
    text: str, target_words: int = DEFAULT_CHUNK_SIZE_WORDS
) -> List[tuple[str, int]]:
    """
    Split text into chunks of approximately target_words each.

    Returns list of (chunk_text, word_count) for each chunk.
    """
    if not text or not text.strip():
        return []
    words = text.strip().split()
    if not words:
        return []
    result: List[tuple[str, int]] = []
    current: List[str] = []
    current_count = 0
    for word in words:
        current.append(word)
        current_count += 1
        if current_count >= target_words:
            result.append((" ".join(current), current_count))
            current = []
            current_count = 0
    if current:
        result.append((" ".join(current), current_count))
    return result


def _normalize_url_for_crawl(url: str) -> str:
    """Strip fragment and trailing slash for dedup; keep scheme and netloc."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        normalized += "?" + parsed.query
    return normalized


def _same_domain(base_url: str, link_url: str) -> bool:
    """True if link_url is same scheme+netloc as base_url (or relative)."""
    if not link_url or link_url.startswith(("#", "mailto:", "tel:", "javascript:")):
        return False
    parsed_base = urlparse(base_url)
    parsed_link = urlparse(link_url)
    if not parsed_link.netloc:
        return True
    return (
        parsed_link.scheme == parsed_base.scheme
        and parsed_link.netloc == parsed_base.netloc
    )


# Extensions we skip when crawling (binary or non-page resources)
_NON_HTML_EXTENSIONS = frozenset(
    (
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".zip",
        ".tar",
        ".gz",
        ".css",
        ".js",
        ".json",
        ".xml",
        ".rss",
        ".mp3",
        ".mp4",
        ".webm",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    )
)


def _extract_same_domain_links(soup: BeautifulSoup, current_url: str) -> List[str]:
    """Return absolute same-domain URLs from <a href>, normalized and deduped. Skips non-HTML resources."""
    seen: set[str] = set()
    out: List[str] = []
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(current_url, href)
        if not _same_domain(current_url, absolute):
            continue
        path_lower = urlparse(absolute).path.lower()
        if any(path_lower.endswith(ext) for ext in _NON_HTML_EXTENSIONS):
            continue
        normalized = _normalize_url_for_crawl(absolute)
        if normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def _fetch_with_browser_sync(url: str, timeout_seconds: float | None = None) -> str:
    """
    Fetch page HTML using undetected headless Chrome (bypasses Cloudflare/bot blocks).
    Runs synchronously; call via asyncio.to_thread() from async code.
    Set CHROME_VERSION_MAIN to your Chrome major version (e.g. 143) if you see
    "This version of ChromeDriver only supports Chrome version X" and your Chrome is different.

    Args:
        url: URL to fetch
        timeout_seconds: Page load timeout. If None, uses settings.browser_page_load_timeout_seconds
    """
    import undetected_chromedriver as uc

    # Use settings if timeout not explicitly provided
    if timeout_seconds is None:
        settings = get_settings()
        timeout_seconds = settings.browser_page_load_timeout_seconds

    options = uc.ChromeOptions()
    options.headless = True
    version_main = os.environ.get("CHROME_VERSION_MAIN")
    kwargs = {"options": options}
    if version_main is not None:
        try:
            kwargs["version_main"] = int(version_main)
        except ValueError:
            pass
    driver = uc.Chrome(**kwargs)
    try:
        driver.set_page_load_timeout(timeout_seconds)
        driver.get(url)
        return driver.page_source
    finally:
        driver.quit()


async def _fetch_one_page(url: str, headers: dict) -> str:
    """
    Fetch one URL. Tries httpx first; on 403/503 falls back to undetected Chrome.
    Raises ValueError on failure.

    Uses configurable timeouts from settings:
    - scraper_timeout_seconds for httpx requests
    - browser_page_load_timeout_seconds for browser fallback
    """
    settings = get_settings()
    html: str | None = None
    try:
        async with httpx.AsyncClient(
            timeout=settings.scraper_timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            logfire.info(
                "Page fetched (httpx)",
                url=url,
                status_code=response.status_code,
                content_length=len(html),
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (403, 503):
            logfire.info(
                "httpx blocked, falling back to browser",
                url=url,
                status_code=e.response.status_code,
            )
            html = await asyncio.to_thread(
                _fetch_with_browser_sync,
                url,
                settings.browser_page_load_timeout_seconds,
            )
            logfire.info("Page fetched via browser", url=url, content_length=len(html))
        else:
            raise ValueError(f"Failed to fetch {url}: {e}") from e
    except httpx.HTTPError as e:
        raise ValueError(f"Failed to fetch {url}: {e}") from e
    if not html:
        raise ValueError(f"Failed to fetch {url}: no content")
    return html


def _parse_page_text_and_links(
    html: str, current_url: str
) -> tuple[str, List[str], str]:
    """
    Parse HTML: extract visible text (nav/footer removed), same-domain links, and title.
    Returns (normalized_text, list_of_absolute_same_domain_urls, page_title).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text()
    text = re.sub(r"\s+", " ", text).strip()
    links = _extract_same_domain_links(soup, current_url)
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    return text, links, title


async def scrape_website(
    url: str, max_pages: int = DEFAULT_MAX_SCRAPE_PAGES
) -> ScrapeResult:
    """
    Scrape website and return per-page data plus text chunks from multiple same-domain pages.
    Discovers internal links from each page and crawls up to max_pages.
    Tries httpx first per page; on 403/503 (e.g. Cloudflare) falls back to undetected Chrome.

    Args:
        url: Root URL to scrape (start page)
        max_pages: Maximum number of pages to scrape (default 20 for richer reference docs)

    Returns:
        ScrapeResult with pages (URL, title, content per page), chunks, and content_hash
    """
    start_time = time.time()
    normalized_start = _normalize_url_for_crawl(url)
    logfire.info(
        "Starting website scrape (multi-page)",
        url=normalized_start,
        max_pages=max_pages,
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    visited: set[str] = set()
    to_visit: List[str] = [url]  # exact start URL so first fetch matches user/tests
    in_queue: set[str] = {_normalize_url_for_crawl(url)}
    pages: List[ScrapedPage] = []

    while to_visit and len(visited) < max_pages:
        current = to_visit.pop(0)
        current_normalized = _normalize_url_for_crawl(current)
        if current_normalized in visited:
            continue
        visited.add(current_normalized)

        try:
            html = await _fetch_one_page(current, headers)
        except ValueError:
            if not pages:
                raise
            logfire.warning("Skipping page after fetch error", url=current)
            continue

        text, new_links, title = _parse_page_text_and_links(html, current)
        # If first page has very little text (likely JS-rendered SPA), refetch with browser
        if len(visited) == 1 and len(text.split()) < MIN_JS_RENDERED_PAGE_WORDS:
            logfire.info(
                "First page has little text, refetching with browser (likely JS-rendered)",
                url=current,
                word_count=len(text.split()),
            )
            try:
                settings = get_settings()
                html = await asyncio.to_thread(
                    _fetch_with_browser_sync,
                    current,
                    settings.browser_js_refetch_timeout_seconds,
                )
                text, new_links, title = _parse_page_text_and_links(html, current)
            except Exception as e:
                logfire.warning(
                    "Browser refetch failed, using initial content",
                    url=current,
                    error=str(e),
                )
        if text:
            word_count = len(text.split())
            pages.append(
                ScrapedPage(
                    url=current,
                    normalized_url=current_normalized,
                    title=title,
                    content=text,
                    word_count=word_count,
                    scraped_at=datetime.now(timezone.utc),
                )
            )

        for link in new_links:
            link_norm = _normalize_url_for_crawl(link)
            if link_norm not in visited and link_norm not in in_queue:
                in_queue.add(link_norm)
                to_visit.append(link)

        # Polite delay between requests
        if to_visit and len(visited) < max_pages:
            await asyncio.sleep(POLITE_REQUEST_DELAY_SECONDS)

    page_texts = [p.content for p in pages]
    combined_text = " ".join(page_texts)
    combined_text = re.sub(r"\s+", " ", combined_text).strip()

    content_hash = hashlib.sha256(combined_text.encode()).hexdigest()

    # Use the centralized chunk_text() function instead of inline duplication
    chunk_tuples = chunk_text(combined_text, target_words=DEFAULT_CHUNK_SIZE_WORDS)
    chunks = [chunk for chunk, _ in chunk_tuples]

    total_elapsed = time.time() - start_time
    total_words = len(combined_text.split())
    chunk_sizes = [len(c.split()) for c in chunks]
    avg_chunk = sum(chunk_sizes) / len(chunks) if chunks else 0
    logfire.info(
        "Website scrape completed",
        url=normalized_start,
        pages_scraped=len(visited),
        total_words=total_words,
        chunk_count=len(chunks),
        avg_chunk_size_words=avg_chunk,
        content_hash=content_hash,
        total_time_ms=total_elapsed * 1000,
    )
    return ScrapeResult(pages=pages, chunks=chunks, content_hash=content_hash)
