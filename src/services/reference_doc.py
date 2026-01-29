"""Build reference document via Copilot service."""

import hashlib

from src.services.copilot_service import CopilotService


async def build_reference_doc(
    copilot: CopilotService,
    website_url: str,
    text_chunks: list[str],
) -> tuple[str, str]:
    """
    Build reference document from text chunks using Copilot.
    
    Args:
        copilot: CopilotService instance
        website_url: Source website URL
        text_chunks: List of text chunks from scraping
        
    Returns:
        Tuple of (markdown_content, content_hash)
    """
    # Synthesize reference document
    markdown_content = await copilot.synthesize_reference(website_url, text_chunks)
    
    # Generate content hash
    content_hash = hashlib.sha256(markdown_content.encode()).hexdigest()
    
    return markdown_content, content_hash
