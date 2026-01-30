"""Website scraping service with separated responsibilities.

This module refactors the monolithic scrape_website function into smaller,
testable, single-responsibility components:
- PageFetcher: Protocol and implementation for fetching page content
- PageParser: Extract text and links from HTML
- TextChunker: Split text into chunks of target word count
- WebsiteScraper: Coordinate scraping operations

Each component can be mocked independently for testing.
"""

import asyncio
import hashlib
import os
import re
import time
from datetime import datetime, timezone
from typing import List, Protocol
from urllib.parse import urljoin, urlparse

import httpx
import logfire
from bs4 import BeautifulSoup

from src.constants import (
    BROWSER_JS_REFETCH_TIMEOUT_SECONDS,
    BROWSER_PAGE_LOAD_TIMEOUT_SECONDS,
    DEFAULT_CHUNK_SIZE_WORDS,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_MAX_SCRAPE_PAGES,
    MIN_JS_RENDERED_PAGE_WORDS,
    POLITE_REQUEST_DELAY_SECONDS,
)
from src.models.scraper_models import ScrapedPage, ScrapeResult


class PageFetcher(Protocol):
    """Protocol for fetching page content."""

    async def fetch(self, url: str) -> str:
        """Fetch HTML content from URL.

        Args:
            url: The URL to fetch

        Returns:
            HTML content as string

        Raises:
            ValueError: If the fetch fails
        """
        ...

    async def fetch_with_browser(self, url: str, timeout: float | None = None) -> str:
        """Fetch page using browser automation (for JS-rendered pages).

        Args:
            url: The URL to fetch
            timeout: Optional timeout in seconds

        Returns:
            HTML content as string

        Raises:
            Exception: If browser fetch fails
        """
        ...


class HttpxPageFetcher:
    """Fetch pages using httpx with browser fallback for blocked requests."""

    # Default headers to mimic a real browser
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(
        self,
        timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        headers: dict[str, str] | None = None,
    ):
        """Initialize the page fetcher.

        Args:
            timeout: HTTP timeout in seconds
            headers: Optional custom headers (defaults to browser-like headers)
        """
        self._timeout = timeout
        self._headers = headers or self.DEFAULT_HEADERS.copy()

    async def fetch(self, url: str) -> str:
        """Fetch page, falling back to browser on 403/503.

        Args:
            url: The URL to fetch

        Returns:
            HTML content as string

        Raises:
            ValueError: If fetch fails (after browser fallback attempt if applicable)
        """
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers=self._headers,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                logfire.info(
                    "Page fetched (httpx)",
                    url=url,
                    status_code=response.status_code,
                    content_length=len(response.text),
                )
                return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 503):
                logfire.info(
                    "httpx blocked, falling back to browser",
                    url=url,
                    status_code=e.response.status_code,
                )
                return await self.fetch_with_browser(
                    url, BROWSER_PAGE_LOAD_TIMEOUT_SECONDS
                )
            raise ValueError(f"Failed to fetch {url}: {e}") from e
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch {url}: {e}") from e

    async def fetch_with_browser(self, url: str, timeout: float | None = None) -> str:
        """Fetch using undetected Chrome for JS-rendered or bot-blocked pages.

        Args:
            url: The URL to fetch
            timeout: Optional timeout in seconds (defaults to BROWSER_PAGE_LOAD_TIMEOUT_SECONDS)

        Returns:
            HTML content as string
        """
        timeout = timeout or BROWSER_PAGE_LOAD_TIMEOUT_SECONDS
        html = await asyncio.to_thread(self._fetch_with_browser_sync, url, timeout)
        logfire.info("Page fetched via browser", url=url, content_length=len(html))
        return html

    @staticmethod
    def _fetch_with_browser_sync(url: str, timeout_seconds: float) -> str:
        """Synchronous browser fetch using undetected Chrome.

        Set CHROME_VERSION_MAIN to your Chrome major version (e.g. 143) if you see
        "This version of ChromeDriver only supports Chrome version X".
        """
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        options.headless = True
        version_main = os.environ.get("CHROME_VERSION_MAIN")
        kwargs: dict = {"options": options}
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


class PageParser:
    """Parse HTML pages to extract text and links."""

    # Extensions to skip when crawling (binary or non-page resources)
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

    def parse(self, html: str, current_url: str) -> tuple[str, List[str], str]:
        """Parse HTML and extract text, links, and title.

        Args:
            html: Raw HTML content
            current_url: The URL the HTML was fetched from (for resolving relative links)

        Returns:
            Tuple of (normalized_text, same_domain_links, page_title)
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        # Extract text
        text = soup.get_text()
        text = re.sub(r"\s+", " ", text).strip()

        # Extract links
        links = self._extract_links(soup, current_url)

        # Extract title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        return text, links, title

    def _extract_links(self, soup: BeautifulSoup, current_url: str) -> List[str]:
        """Extract same-domain links from page.

        Args:
            soup: BeautifulSoup parsed HTML
            current_url: Base URL for resolving relative links

        Returns:
            List of absolute same-domain URLs, normalized and deduplicated
        """
        seen: set[str] = set()
        out: List[str] = []

        for a in soup.find_all("a", href=True):
            href = (a["href"] or "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            absolute = urljoin(current_url, href)
            if not self._is_same_domain(current_url, absolute):
                continue

            path_lower = urlparse(absolute).path.lower()
            if any(path_lower.endswith(ext) for ext in self._NON_HTML_EXTENSIONS):
                continue

            normalized = self.normalize_url(absolute)
            if normalized not in seen:
                seen.add(normalized)
                out.append(normalized)

        return out

    def _is_same_domain(self, base_url: str, link_url: str) -> bool:
        """Check if link is same domain as base.

        Args:
            base_url: The base URL to compare against
            link_url: The link URL to check

        Returns:
            True if same domain (or relative), False otherwise
        """
        parsed_base = urlparse(base_url)
        parsed_link = urlparse(link_url)
        if not parsed_link.netloc:
            return True
        return (
            parsed_link.scheme == parsed_base.scheme
            and parsed_link.netloc == parsed_base.netloc
        )

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL for deduplication.

        Strips fragments and trailing slashes while preserving query strings.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL string
        """
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized += "?" + parsed.query
        return normalized


class TextChunker:
    """Chunk text into segments of target word count."""

    def __init__(self, target_words: int = DEFAULT_CHUNK_SIZE_WORDS):
        """Initialize the text chunker.

        Args:
            target_words: Target number of words per chunk
        """
        self._target_words = target_words

    def chunk(self, text: str) -> List[tuple[str, int]]:
        """Split text into chunks.

        Args:
            text: Text to split into chunks

        Returns:
            List of (chunk_text, word_count) tuples
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
            if current_count >= self._target_words:
                result.append((" ".join(current), current_count))
                current = []
                current_count = 0

        if current:
            result.append((" ".join(current), current_count))

        return result

    def chunk_to_strings(self, text: str) -> List[str]:
        """Split text into chunks, returning only the chunk strings.

        Args:
            text: Text to split into chunks

        Returns:
            List of chunk strings (without word counts)
        """
        return [chunk for chunk, _ in self.chunk(text)]


class WebsiteScraper:
    """Coordinate website scraping operations.

    This class orchestrates the scraping workflow:
    1. Crawl pages starting from a root URL
    2. Parse each page to extract text and discover links
    3. Combine all page content and chunk it

    Components (fetcher, parser, chunker) can be injected for testing.
    """

    def __init__(
        self,
        max_pages: int = DEFAULT_MAX_SCRAPE_PAGES,
        fetcher: PageFetcher | None = None,
        parser: PageParser | None = None,
        chunker: TextChunker | None = None,
    ):
        """Initialize the website scraper.

        Args:
            max_pages: Maximum number of pages to scrape
            fetcher: Page fetcher implementation (defaults to HttpxPageFetcher)
            parser: Page parser implementation (defaults to PageParser)
            chunker: Text chunker implementation (defaults to TextChunker)
        """
        self._max_pages = max_pages
        self._fetcher = fetcher or HttpxPageFetcher()
        self._parser = parser or PageParser()
        self._chunker = chunker or TextChunker()

    async def scrape(self, url: str) -> ScrapeResult:
        """Scrape website and return structured result.

        Args:
            url: Root URL to start scraping

        Returns:
            ScrapeResult with pages, chunks, and content_hash
        """
        start_time = time.time()
        normalized_start = self._parser.normalize_url(url)
        logfire.info(
            "Starting website scrape (WebsiteScraper)",
            url=normalized_start,
            max_pages=self._max_pages,
        )

        pages = await self._crawl_pages(url)

        # Combine all page content
        combined_text = " ".join(p.content for p in pages)
        combined_text = re.sub(r"\s+", " ", combined_text).strip()

        # Create chunks using the chunker
        chunks = self._chunker.chunk_to_strings(combined_text)

        # Compute content hash
        content_hash = hashlib.sha256(combined_text.encode()).hexdigest()

        elapsed = time.time() - start_time
        total_words = len(combined_text.split())
        chunk_sizes = [len(c.split()) for c in chunks]
        avg_chunk = sum(chunk_sizes) / len(chunks) if chunks else 0

        logfire.info(
            "Website scrape completed (WebsiteScraper)",
            url=normalized_start,
            pages_scraped=len(pages),
            total_words=total_words,
            chunk_count=len(chunks),
            avg_chunk_size_words=avg_chunk,
            content_hash=content_hash,
            total_time_ms=elapsed * 1000,
        )

        return ScrapeResult(pages=pages, chunks=chunks, content_hash=content_hash)

    async def _crawl_pages(self, start_url: str) -> List[ScrapedPage]:
        """Crawl pages starting from URL.

        Args:
            start_url: URL to start crawling from

        Returns:
            List of ScrapedPage objects
        """
        visited: set[str] = set()
        to_visit: List[str] = [start_url]
        in_queue: set[str] = {self._parser.normalize_url(start_url)}
        pages: List[ScrapedPage] = []

        while to_visit and len(visited) < self._max_pages:
            current = to_visit.pop(0)
            current_normalized = self._parser.normalize_url(current)

            if current_normalized in visited:
                continue
            visited.add(current_normalized)

            try:
                html = await self._fetcher.fetch(current)
            except ValueError:
                if not pages:
                    raise
                logfire.warning("Skipping page after fetch error", url=current)
                continue

            text, new_links, title = self._parser.parse(html, current)

            # Handle JS-rendered pages: if first page has little text, refetch with browser
            if len(visited) == 1 and len(text.split()) < MIN_JS_RENDERED_PAGE_WORDS:
                logfire.info(
                    "First page has little text, refetching with browser (likely JS-rendered)",
                    url=current,
                    word_count=len(text.split()),
                )
                try:
                    html = await self._fetcher.fetch_with_browser(
                        current, BROWSER_JS_REFETCH_TIMEOUT_SECONDS
                    )
                    text, new_links, title = self._parser.parse(html, current)
                except Exception as e:
                    logfire.warning(
                        "Browser refetch failed, using initial content",
                        url=current,
                        error=str(e),
                    )

            if text:
                pages.append(
                    ScrapedPage(
                        url=current,
                        normalized_url=current_normalized,
                        title=title,
                        content=text,
                        word_count=len(text.split()),
                        scraped_at=datetime.now(timezone.utc),
                    )
                )

            # Add new links to queue
            for link in new_links:
                link_norm = self._parser.normalize_url(link)
                if link_norm not in visited and link_norm not in in_queue:
                    in_queue.add(link_norm)
                    to_visit.append(link)

            # Polite delay between requests
            if to_visit and len(visited) < self._max_pages:
                await asyncio.sleep(POLITE_REQUEST_DELAY_SECONDS)

        return pages


# =============================================================================
# Factory function for backward compatibility
# =============================================================================


async def scrape_website_v2(
    url: str,
    max_pages: int = DEFAULT_MAX_SCRAPE_PAGES,
) -> ScrapeResult:
    """Scrape website using the new WebsiteScraper class.

    This is a backward-compatible wrapper function that uses the refactored
    WebsiteScraper implementation.

    Args:
        url: Root URL to scrape
        max_pages: Maximum number of pages to scrape (default 20)

    Returns:
        ScrapeResult with pages, chunks, and content_hash
    """
    scraper = WebsiteScraper(max_pages=max_pages)
    return await scraper.scrape(url)
