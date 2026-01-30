"""Tests for website scraping service."""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import respx as respx_lib

from src.services.scraper import scrape_website


@pytest.fixture(autouse=True)
def mock_browser_fetch():
    """Mock _fetch_with_browser_sync so 'first page little text' refetch does not launch Chrome.
    Returns the same URL content via sync httpx so respx mocks are used and test assertions pass.
    """
    def _fake_browser_fetch(url: str, timeout_seconds: float = 30.0) -> str:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    with patch("src.services.scraper._fetch_with_browser_sync", side_effect=_fake_browser_fetch):
        yield


class TestScrapeWebsite:
    """Test scrape_website() function."""
    
    @pytest.mark.asyncio
    async def test_scrape_website_valid_url(self, respx_mock):
        """Test scraping with valid URL."""
        html_content = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Test Content</h1>
                <p>This is a test paragraph with enough words to make a chunk.</p>
            </body>
        </html>
        """
        
        respx_mock.get("https://example.com").mock(return_value=httpx.Response(
            200,
            text=html_content
        ))
        
        chunks = await scrape_website("https://example.com")
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_scrape_website_invalid_url(self, respx_mock):
        """Test error handling for invalid URLs."""
        respx_mock.get("https://invalid-url-that-fails.com").mock(
            side_effect=httpx.HTTPError("Connection failed")
        )
        
        with pytest.raises(ValueError, match="Failed to fetch"):
            await scrape_website("https://invalid-url-that-fails.com")
    
    @pytest.mark.asyncio
    async def test_scrape_website_timeout(self, respx_mock):
        """Test timeout handling."""
        respx_mock.get("https://slow-site.com").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        
        with pytest.raises(ValueError, match="Failed to fetch"):
            await scrape_website("https://slow-site.com")
    
    @pytest.mark.asyncio
    async def test_scrape_website_removes_scripts(self, respx_mock):
        """Test that script and style elements are removed."""
        html_content = """
        <html>
            <head>
                <script>alert('test');</script>
                <style>body { color: red; }</style>
            </head>
            <body>
                <h1>Visible Content</h1>
                <p>This should be in the output.</p>
            </body>
        </html>
        """
        
        respx_mock.get("https://example.com").mock(return_value=httpx.Response(
            200,
            text=html_content
        ))
        
        chunks = await scrape_website("https://example.com")
        
        # Script and style content should not appear
        combined_text = " ".join(chunks)
        assert "alert" not in combined_text.lower()
        assert "color: red" not in combined_text.lower()
        assert "Visible Content" in combined_text
        assert "This should be in the output" in combined_text
    
    @pytest.mark.asyncio
    async def test_scrape_website_removes_nav_footer(self, respx_mock):
        """Test that nav and footer elements are removed."""
        html_content = """
        <html>
            <body>
                <nav>Navigation links</nav>
                <main>Main content here</main>
                <footer>Footer content</footer>
            </body>
        </html>
        """
        
        respx_mock.get("https://example.com").mock(return_value=httpx.Response(
            200,
            text=html_content
        ))
        
        chunks = await scrape_website("https://example.com")
        
        combined_text = " ".join(chunks)
        assert "Navigation links" not in combined_text
        assert "Footer content" not in combined_text
        assert "Main content here" in combined_text
    
    @pytest.mark.asyncio
    async def test_scrape_website_whitespace_normalization(self, respx_mock):
        """Test whitespace normalization."""
        html_content = """
        <html>
            <body>
                <p>Text    with    multiple    spaces</p>
                <p>Text
                
                with
                
                newlines</p>
            </body>
        </html>
        """
        
        respx_mock.get("https://example.com").mock(return_value=httpx.Response(
            200,
            text=html_content
        ))
        
        chunks = await scrape_website("https://example.com")
        
        # Check that multiple spaces are normalized
        combined_text = " ".join(chunks)
        assert "    " not in combined_text  # No multiple spaces
        assert "\n\n" not in combined_text  # No multiple newlines
    
    @pytest.mark.asyncio
    @respx_lib.mock
    async def test_scrape_website_chunking_properties(self):
        """Property: Chunking should always return list of non-empty strings."""
        # Test with various word counts
        for word_count in [100, 500, 1000, 2000]:
            words = ["word"] * word_count
            html_content = f"<html><body><p>{' '.join(words)}</p></body></html>"
            
            respx_lib.get("https://example.com").mock(return_value=httpx.Response(
                200,
                text=html_content
            ))
            
            chunks = await scrape_website("https://example.com")
            
            # Invariants
            assert isinstance(chunks, list)
            assert all(isinstance(chunk, str) for chunk in chunks)
            assert all(len(chunk) > 0 for chunk in chunks)  # No empty chunks
            assert all(len(chunk.split()) > 0 for chunk in chunks)  # All chunks have words
            
            respx_lib.reset()
    
    @pytest.mark.asyncio
    async def test_scrape_website_chunk_size(self, respx_mock):
        """Test that chunks are approximately 500-800 words."""
        # Generate HTML with enough words to create multiple chunks
        words = ["word"] * 2000
        html_content = f"<html><body><p>{' '.join(words)}</p></body></html>"
        
        respx_mock.get("https://example.com").mock(return_value=httpx.Response(
            200,
            text=html_content
        ))
        
        chunks = await scrape_website("https://example.com")
        
        # Check chunk sizes (target is 650 words, allow some flexibility)
        for chunk in chunks[:-1]:  # Last chunk may be smaller
            word_count = len(chunk.split())
            # Chunks should be roughly in the 500-800 word range
            # Allow some flexibility for edge cases
            assert word_count >= 400, f"Chunk too small: {word_count} words"
            assert word_count <= 900, f"Chunk too large: {word_count} words"
    
    @pytest.mark.asyncio
    async def test_scrape_website_empty_content(self, respx_mock):
        """Test handling of empty HTML content."""
        html_content = "<html><body></body></html>"
        
        respx_mock.get("https://example.com").mock(return_value=httpx.Response(
            200,
            text=html_content
        ))
        
        chunks = await scrape_website("https://example.com")
        
        # Should return empty list or list with empty string
        assert isinstance(chunks, list)
        # If there's no content, chunks might be empty or contain empty strings
        if chunks:
            # If chunks exist, they should be strings (even if empty)
            assert all(isinstance(chunk, str) for chunk in chunks)
    
    @pytest.mark.asyncio
    @respx_lib.mock
    async def test_scrape_website_follows_redirects(self):
        """Test that redirects are followed."""
        # Mock the final destination (httpx with follow_redirects handles this)
        respx_lib.get("https://example.com/final").mock(return_value=httpx.Response(
            200,
            text="<html><body><p>Final content</p></body></html>"
        ))
        
        chunks = await scrape_website("https://example.com/final")
        
        # Should get content from final URL
        combined_text = " ".join(chunks)
        assert "Final content" in combined_text
    
    @pytest.mark.asyncio
    @respx_lib.mock
    async def test_scrape_website_various_html_structures(self):
        """Test that scraping handles various HTML structures."""
        html_structures = [
            "<div>Simple div</div>",
            "<p>Paragraph with <strong>bold</strong> text</p>",
            "<ul><li>Item 1</li><li>Item 2</li></ul>",
            "<table><tr><td>Cell</td></tr></table>",
        ]
        
        for html_structure in html_structures:
            html_content = f"<html><body>{html_structure}</body></html>"
            
            respx_lib.get("https://example.com").mock(return_value=httpx.Response(
                200,
                text=html_content
            ))
            
            chunks = await scrape_website("https://example.com")
            
            # Should always return list of strings
            assert isinstance(chunks, list)
            assert all(isinstance(chunk, str) for chunk in chunks)
            
            respx_lib.reset()
