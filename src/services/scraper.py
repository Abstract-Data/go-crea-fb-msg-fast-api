"""Website scraping and chunking service."""

import re
from typing import List

import httpx
from bs4 import BeautifulSoup


async def scrape_website(url: str, max_pages: int = 5) -> List[str]:
    """
    Scrape website and return text chunks.
    
    Args:
        url: Root URL to scrape
        max_pages: Maximum number of pages to scrape
        
    Returns:
        List of text chunks (500-800 words each)
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch {url}: {e}")
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer"]):
        script.decompose()
    
    # Extract text
    text = soup.get_text()
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Chunk into 500-800 word segments
    words = text.split()
    chunks = []
    current_chunk = []
    current_word_count = 0
    target_words = 650  # Target middle of 500-800 range
    
    for word in words:
        current_chunk.append(word)
        current_word_count += 1
        
        if current_word_count >= target_words:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_word_count = 0
    
    # Add remaining words
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks
