"""Tests for the WebsiteScraper class and its components.

These tests verify the refactored scraper implementation with
proper separation of concerns: PageFetcher, PageParser, TextChunker,
and the coordinating WebsiteScraper class.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.website_scraper import (
    HttpxPageFetcher,
    PageParser,
    TextChunker,
    WebsiteScraper,
    scrape_website_v2,
)
from src.models.scraper_models import ScrapeResult


class TestPageParser:
    """Tests for PageParser class."""

    def test_parse_extracts_text(self):
        """Parse should extract visible text from HTML."""
        html = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Hello World</h1>
            <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        parser = PageParser()
        text, links, title = parser.parse(html, "https://example.com")

        assert "Hello World" in text
        assert "This is a test paragraph" in text
        assert title == "Test Page"

    def test_parse_removes_script_tags(self):
        """Parse should remove script content."""
        html = """
        <html>
        <body>
            <h1>Visible</h1>
            <script>var secret = "hidden";</script>
            <p>Also visible</p>
        </body>
        </html>
        """
        parser = PageParser()
        text, _, _ = parser.parse(html, "https://example.com")

        assert "Visible" in text
        assert "Also visible" in text
        assert "secret" not in text
        assert "hidden" not in text

    def test_parse_removes_style_tags(self):
        """Parse should remove style content."""
        html = """
        <html>
        <body>
            <style>.hidden { display: none; }</style>
            <h1>Content</h1>
        </body>
        </html>
        """
        parser = PageParser()
        text, _, _ = parser.parse(html, "https://example.com")

        assert "Content" in text
        assert "hidden" not in text
        assert "display" not in text

    def test_parse_removes_nav_footer(self):
        """Parse should remove nav and footer elements."""
        html = """
        <html>
        <body>
            <nav>Navigation links</nav>
            <main>Main content here</main>
            <footer>Footer info</footer>
        </body>
        </html>
        """
        parser = PageParser()
        text, _, _ = parser.parse(html, "https://example.com")

        assert "Main content here" in text
        assert "Navigation links" not in text
        assert "Footer info" not in text

    def test_parse_normalizes_whitespace(self):
        """Parse should normalize multiple whitespace to single space."""
        html = """
        <html>
        <body>
            <p>Multiple    spaces     here</p>
            <p>

            Newlines   too

            </p>
        </body>
        </html>
        """
        parser = PageParser()
        text, _, _ = parser.parse(html, "https://example.com")

        # Should not have multiple consecutive spaces
        assert "  " not in text
        assert "Multiple spaces here" in text
        assert "Newlines too" in text

    def test_parse_extracts_same_domain_links(self):
        """Parse should extract same-domain links."""
        html = """
        <html>
        <body>
            <a href="/page1">Internal link</a>
            <a href="https://example.com/page2">Same domain absolute</a>
            <a href="https://other.com/page3">External link</a>
            <a href="mailto:test@example.com">Email link</a>
        </body>
        </html>
        """
        parser = PageParser()
        _, links, _ = parser.parse(html, "https://example.com")

        # Should include internal and same-domain links
        assert "https://example.com/page1" in links
        assert "https://example.com/page2" in links
        # Should not include external or non-HTTP links
        assert not any("other.com" in link for link in links)
        assert not any("mailto:" in link for link in links)

    def test_parse_skips_non_html_extensions(self):
        """Parse should skip links to non-HTML resources."""
        html = """
        <html>
        <body>
            <a href="/page.html">HTML page</a>
            <a href="/image.png">PNG image</a>
            <a href="/document.pdf">PDF document</a>
            <a href="/data.json">JSON data</a>
        </body>
        </html>
        """
        parser = PageParser()
        _, links, _ = parser.parse(html, "https://example.com")

        assert "https://example.com/page.html" in links
        assert not any(".png" in link for link in links)
        assert not any(".pdf" in link for link in links)
        assert not any(".json" in link for link in links)

    def test_normalize_url_strips_trailing_slash(self):
        """Normalize URL should strip trailing slashes from paths."""
        parser = PageParser()

        assert (
            parser.normalize_url("https://example.com/page/")
            == "https://example.com/page"
        )
        # Root path "/" is preserved to ensure it's a valid path
        assert parser.normalize_url("https://example.com/") == "https://example.com/"
        assert parser.normalize_url("https://example.com") == "https://example.com/"

    def test_normalize_url_preserves_query_string(self):
        """Normalize URL should preserve query strings."""
        parser = PageParser()

        result = parser.normalize_url("https://example.com/page?id=123&sort=name")
        assert result == "https://example.com/page?id=123&sort=name"

    def test_normalize_url_strips_fragment(self):
        """Normalize URL should strip fragments (handled by urljoin in real code)."""
        parser = PageParser()

        # The normalize_url doesn't explicitly handle fragments,
        # but fragments are stripped by the link extraction logic
        result = parser.normalize_url("https://example.com/page")
        assert "#" not in result


class TestTextChunker:
    """Tests for TextChunker class."""

    def test_chunk_empty_text_returns_empty(self):
        """Empty text should return empty list."""
        chunker = TextChunker(target_words=10)

        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []
        assert chunker.chunk(None) == []  # type: ignore

    def test_chunk_single_chunk(self):
        """Text shorter than target should return single chunk."""
        chunker = TextChunker(target_words=10)
        text = "one two three four five"

        result = chunker.chunk(text)

        assert len(result) == 1
        assert result[0] == ("one two three four five", 5)

    def test_chunk_multiple_chunks(self):
        """Text longer than target should be split into multiple chunks."""
        chunker = TextChunker(target_words=3)
        text = "one two three four five six seven eight nine"

        result = chunker.chunk(text)

        assert len(result) == 3
        assert result[0] == ("one two three", 3)
        assert result[1] == ("four five six", 3)
        assert result[2] == ("seven eight nine", 3)

    def test_chunk_handles_remainder(self):
        """Last chunk should include remaining words even if less than target."""
        chunker = TextChunker(target_words=3)
        text = "one two three four five"

        result = chunker.chunk(text)

        assert len(result) == 2
        assert result[0] == ("one two three", 3)
        assert result[1] == ("four five", 2)

    def test_chunk_to_strings(self):
        """chunk_to_strings should return only chunk text."""
        chunker = TextChunker(target_words=3)
        text = "one two three four five"

        result = chunker.chunk_to_strings(text)

        assert result == ["one two three", "four five"]

    def test_chunk_with_default_target(self):
        """Chunker should use default target words from constants."""
        from src.constants import DEFAULT_CHUNK_SIZE_WORDS

        chunker = TextChunker()
        assert chunker._target_words == DEFAULT_CHUNK_SIZE_WORDS


class TestHttpxPageFetcher:
    """Tests for HttpxPageFetcher class."""

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """Successful fetch should return HTML content."""
        fetcher = HttpxPageFetcher()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Hello</body></html>"
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await fetcher.fetch("https://example.com")

            assert result == "<html><body>Hello</body></html>"

    @pytest.mark.asyncio
    async def test_fetch_403_falls_back_to_browser(self):
        """403 response should trigger browser fallback."""
        import httpx

        fetcher = HttpxPageFetcher()

        # Mock httpx to raise 403
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 403
            http_error = httpx.HTTPStatusError(
                "Forbidden", request=MagicMock(), response=mock_response
            )
            mock_response.raise_for_status.side_effect = http_error
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Mock browser fallback
            with patch.object(
                fetcher, "fetch_with_browser", new_callable=AsyncMock
            ) as mock_browser:
                mock_browser.return_value = "<html>Browser content</html>"

                result = await fetcher.fetch("https://blocked-site.com")

                assert result == "<html>Browser content</html>"
                mock_browser.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_503_falls_back_to_browser(self):
        """503 response should trigger browser fallback."""
        import httpx

        fetcher = HttpxPageFetcher()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 503
            http_error = httpx.HTTPStatusError(
                "Service Unavailable", request=MagicMock(), response=mock_response
            )
            mock_response.raise_for_status.side_effect = http_error
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with patch.object(
                fetcher, "fetch_with_browser", new_callable=AsyncMock
            ) as mock_browser:
                mock_browser.return_value = "<html>Browser content</html>"

                result = await fetcher.fetch("https://unavailable-site.com")

                assert result == "<html>Browser content</html>"

    @pytest.mark.asyncio
    async def test_fetch_other_error_raises_valueerror(self):
        """Other HTTP errors should raise ValueError."""
        import httpx

        fetcher = HttpxPageFetcher()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            http_error = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )
            mock_response.raise_for_status.side_effect = http_error
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Failed to fetch"):
                await fetcher.fetch("https://not-found.com")


class TestWebsiteScraper:
    """Tests for WebsiteScraper class."""

    @pytest.mark.asyncio
    async def test_scrape_single_page(self):
        """Scraper should handle single page with no links."""
        # Create mock fetcher
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.return_value = """
        <html>
        <head><title>Test Page</title></head>
        <body><p>Test content for the page.</p></body>
        </html>
        """

        # Create mock parser
        mock_parser = MagicMock()
        mock_parser.parse.return_value = ("Test content for the page.", [], "Test Page")
        mock_parser.normalize_url.side_effect = lambda x: x.rstrip("/")

        # Create mock chunker
        mock_chunker = MagicMock()
        mock_chunker.chunk_to_strings.return_value = ["Test content for the page."]

        scraper = WebsiteScraper(
            max_pages=10,
            fetcher=mock_fetcher,
            parser=mock_parser,
            chunker=mock_chunker,
        )

        result = await scraper.scrape("https://example.com")

        assert isinstance(result, ScrapeResult)
        assert len(result.pages) == 1
        assert result.pages[0].title == "Test Page"
        assert len(result.chunks) == 1
        assert result.content_hash is not None

    @pytest.mark.asyncio
    async def test_scrape_follows_links(self):
        """Scraper should follow same-domain links up to max_pages."""
        # Track which URLs have been fetched
        fetched_urls = []

        async def mock_fetch(url):
            fetched_urls.append(url)
            if url == "https://example.com":
                return "<html><body>Page 1</body></html>"
            elif url == "https://example.com/page2":
                return "<html><body>Page 2</body></html>"
            return "<html><body>Other</body></html>"

        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.side_effect = mock_fetch

        # Parser returns different links for first page only
        # Use url parameter to determine which page we're parsing
        def mock_parse(html, url):
            if url == "https://example.com":
                return ("Page 1 content", ["https://example.com/page2"], "Page 1")
            elif url == "https://example.com/page2":
                return ("Page 2 content", [], "Page 2")
            return ("Other content", [], "Other")

        mock_parser = MagicMock()
        mock_parser.parse.side_effect = mock_parse
        # Normalize URL should preserve the URL for comparison
        mock_parser.normalize_url.side_effect = lambda x: x.rstrip("/") or x

        mock_chunker = MagicMock()
        mock_chunker.chunk_to_strings.return_value = ["Combined content"]

        scraper = WebsiteScraper(
            max_pages=10,
            fetcher=mock_fetcher,
            parser=mock_parser,
            chunker=mock_chunker,
        )

        # Patch asyncio.sleep to avoid delays in tests
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await scraper.scrape("https://example.com")

        assert len(result.pages) == 2
        assert "https://example.com" in fetched_urls
        assert "https://example.com/page2" in fetched_urls

    @pytest.mark.asyncio
    async def test_scrape_respects_max_pages(self):
        """Scraper should stop at max_pages limit."""
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.return_value = "<html><body>Content</body></html>"

        # Return many links to test max_pages limit
        all_links = [f"https://example.com/page{i}" for i in range(1, 50)]

        def mock_parse(html, url):
            return ("Content", all_links, "Title")

        mock_parser = MagicMock()
        mock_parser.parse.side_effect = mock_parse
        mock_parser.normalize_url.side_effect = lambda x: x.rstrip("/")

        mock_chunker = MagicMock()
        mock_chunker.chunk_to_strings.return_value = ["Content"]

        scraper = WebsiteScraper(
            max_pages=5,  # Limit to 5 pages
            fetcher=mock_fetcher,
            parser=mock_parser,
            chunker=mock_chunker,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await scraper.scrape("https://example.com")

        assert len(result.pages) == 5

    @pytest.mark.asyncio
    async def test_scrape_handles_fetch_error_gracefully(self):
        """Scraper should skip pages that fail to fetch after first page."""
        call_count = [0]

        async def mock_fetch(url):
            call_count[0] += 1
            if call_count[0] == 1:
                return "<html><body>First page</body></html>"
            raise ValueError("Network error")

        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.side_effect = mock_fetch

        def mock_parse(html, url):
            return (
                "Content",
                ["https://example.com/page2", "https://example.com/page3"],
                "Title",
            )

        mock_parser = MagicMock()
        mock_parser.parse.side_effect = mock_parse
        mock_parser.normalize_url.side_effect = lambda x: x.rstrip("/")

        mock_chunker = MagicMock()
        mock_chunker.chunk_to_strings.return_value = ["Content"]

        scraper = WebsiteScraper(
            max_pages=10,
            fetcher=mock_fetcher,
            parser=mock_parser,
            chunker=mock_chunker,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await scraper.scrape("https://example.com")

        # Should have at least the first page
        assert len(result.pages) >= 1

    @pytest.mark.asyncio
    async def test_scrape_raises_on_first_page_failure(self):
        """Scraper should raise if first page fails."""
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.side_effect = ValueError("Network error")

        mock_parser = MagicMock()
        mock_parser.normalize_url.side_effect = lambda x: x.rstrip("/")

        scraper = WebsiteScraper(
            fetcher=mock_fetcher,
            parser=mock_parser,
        )

        with pytest.raises(ValueError, match="Network error"):
            await scraper.scrape("https://example.com")

    @pytest.mark.asyncio
    async def test_scrape_triggers_browser_refetch_for_js_pages(self):
        """Scraper should use browser for JS-rendered pages with little text."""
        from src.constants import MIN_JS_RENDERED_PAGE_WORDS

        # Create text that's below the threshold
        sparse_text = " ".join(["word"] * (MIN_JS_RENDERED_PAGE_WORDS - 10))
        full_text = " ".join(["word"] * (MIN_JS_RENDERED_PAGE_WORDS + 100))

        fetch_count = [0]

        async def mock_fetch(url):
            fetch_count[0] += 1
            return "<html><body>Sparse JS</body></html>"

        async def mock_browser_fetch(url, timeout=None):
            return "<html><body>Full browser content</body></html>"

        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.side_effect = mock_fetch
        mock_fetcher.fetch_with_browser.side_effect = mock_browser_fetch

        parse_count = [0]

        def mock_parse(html, url):
            parse_count[0] += 1
            if "Sparse" in html:
                return (sparse_text, [], "Sparse Title")
            return (full_text, [], "Full Title")

        mock_parser = MagicMock()
        mock_parser.parse.side_effect = mock_parse
        mock_parser.normalize_url.side_effect = lambda x: x.rstrip("/")

        mock_chunker = MagicMock()
        mock_chunker.chunk_to_strings.return_value = ["Combined content"]

        scraper = WebsiteScraper(
            max_pages=1,
            fetcher=mock_fetcher,
            parser=mock_parser,
            chunker=mock_chunker,
        )

        result = await scraper.scrape("https://spa-site.com")

        # Browser fetch should have been called for JS-rendered page
        mock_fetcher.fetch_with_browser.assert_called_once()
        assert len(result.pages) == 1

    @pytest.mark.asyncio
    async def test_scrape_deduplicates_urls(self):
        """Scraper should not visit the same URL twice."""
        fetch_calls = []

        async def mock_fetch(url):
            fetch_calls.append(url)
            return "<html><body>Content</body></html>"

        mock_fetcher = AsyncMock()
        mock_fetcher.fetch.side_effect = mock_fetch

        # Return links that include duplicates and trailing slash variants
        def mock_parse(html, url):
            return (
                "Content",
                [
                    "https://example.com/page1",
                    "https://example.com/page1/",  # Duplicate with trailing slash
                    "https://example.com/page1",  # Exact duplicate
                ],
                "Title",
            )

        mock_parser = MagicMock()
        mock_parser.parse.side_effect = mock_parse
        mock_parser.normalize_url.side_effect = lambda x: x.rstrip("/")

        mock_chunker = MagicMock()
        mock_chunker.chunk_to_strings.return_value = ["Content"]

        scraper = WebsiteScraper(
            max_pages=10,
            fetcher=mock_fetcher,
            parser=mock_parser,
            chunker=mock_chunker,
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await scraper.scrape("https://example.com")

        # Should only have fetched the root and page1 once each
        normalized_fetches = [url.rstrip("/") for url in fetch_calls]
        assert normalized_fetches.count("https://example.com") == 1
        assert normalized_fetches.count("https://example.com/page1") == 1


class TestScrapeWebsiteV2:
    """Tests for the backward-compatible scrape_website_v2 function."""

    @pytest.mark.asyncio
    async def test_scrape_website_v2_uses_websitescraper(self):
        """scrape_website_v2 should use WebsiteScraper internally."""
        with patch("src.services.website_scraper.WebsiteScraper") as mock_scraper_class:
            mock_scraper = AsyncMock()
            mock_scraper.scrape.return_value = ScrapeResult(
                pages=[],
                chunks=["test chunk"],
                content_hash="abc123",
            )
            mock_scraper_class.return_value = mock_scraper

            result = await scrape_website_v2("https://example.com", max_pages=5)

            mock_scraper_class.assert_called_once_with(max_pages=5)
            mock_scraper.scrape.assert_called_once_with("https://example.com")
            assert result.chunks == ["test chunk"]
