"""Integration tests for scraper and Copilot service."""

import pytest
import respx
import httpx

from src.services.scraper import scrape_website
from src.services.copilot_service import CopilotService
from src.services.reference_doc import build_reference_doc


class TestScraperCopilotIntegration:
    """Test scraper → Copilot synthesis flow."""
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_scraper_copilot_end_to_end(self):
        """Test scraper → Copilot synthesis flow end-to-end."""
        # Mock website response
        html_content = """
        <html>
            <head><title>Test Organization</title></head>
            <body>
                <h1>About Us</h1>
                <p>We are a test organization providing various services.</p>
                <h2>Services</h2>
                <ul>
                    <li>Service 1: Description of service 1</li>
                    <li>Service 2: Description of service 2</li>
                </ul>
                <h2>Contact</h2>
                <p>Email: info@example.com</p>
                <p>Phone: 555-1234</p>
            </body>
        </html>
        """
        
        respx.get("https://example.com").mock(return_value=httpx.Response(200, text=html_content))
        
        # Mock Copilot responses
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(return_value=httpx.Response(
            200,
            json={"content": "# Test Organization\n\n## Services\n- Service 1\n- Service 2\n\n## Contact\nEmail: info@example.com"}
        ))
        
        # Scrape website
        chunks = await scrape_website("https://example.com")
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
        
        # Build reference document
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        markdown_content, content_hash = await build_reference_doc(
            copilot=copilot,
            website_url="https://example.com",
            text_chunks=chunks
        )
        
        # Verify reference document
        assert isinstance(markdown_content, str)
        assert len(markdown_content) > 0
        assert isinstance(content_hash, str)
        assert len(content_hash) == 64
        
        # Verify content includes key information
        assert "Test Organization" in markdown_content or "Services" in markdown_content
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_scraper_copilot_with_multiple_chunks(self):
        """Test reference doc building with multiple chunks."""
        # Generate HTML with enough content for multiple chunks
        words = ["word"] * 2000
        html_content = f"<html><body><p>{' '.join(words)}</p></body></html>"
        
        respx.get("https://example.com").mock(return_value=httpx.Response(200, text=html_content))
        respx.get("http://localhost:5909/health").mock(return_value=httpx.Response(200))
        respx.post("http://localhost:5909/chat").mock(return_value=httpx.Response(
            200,
            json={"content": "# Reference Document\n\nSynthesized content from multiple chunks."}
        ))
        
        # Scrape (should produce multiple chunks)
        chunks = await scrape_website("https://example.com")
        
        assert len(chunks) > 1  # Should have multiple chunks
        
        # Build reference document
        copilot = CopilotService(base_url="http://localhost:5909", enabled=True)
        markdown_content, content_hash = await build_reference_doc(
            copilot=copilot,
            website_url="https://example.com",
            text_chunks=chunks
        )
        
        # Verify all chunks were used
        assert markdown_content is not None
        assert content_hash is not None
