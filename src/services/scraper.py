"""Website scraping and chunking service."""

import hashlib
import re
import time
from typing import List

import httpx
import logfire
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
    start_time = time.time()
    
    logfire.info(
        "Starting website scrape",
        url=url,
        max_pages=max_pages,
    )
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        fetch_start = time.time()
        try:
            response = await client.get(url)
            response.raise_for_status()
            fetch_elapsed = time.time() - fetch_start
            
            logfire.info(
                "Website fetched successfully",
                url=url,
                status_code=response.status_code,
                content_length=len(response.text),
                fetch_time_ms=fetch_elapsed * 1000,
            )
        except httpx.HTTPError as e:
            fetch_elapsed = time.time() - fetch_start
            logfire.error(
                "Website fetch failed",
                url=url,
                error=str(e),
                error_type=type(e).__name__,
                fetch_time_ms=fetch_elapsed * 1000,
            )
            raise ValueError(f"Failed to fetch {url}: {e}")
    
    parse_start = time.time()
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer"]):
        script.decompose()
    
    # Extract text
    text = soup.get_text()
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Calculate content hash
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    
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
    
    parse_elapsed = time.time() - parse_start
    total_elapsed = time.time() - start_time
    
    # Calculate chunk statistics
    chunk_sizes = [len(chunk.split()) for chunk in chunks]
    avg_chunk_size = sum(chunk_sizes) / len(chunks) if chunks else 0
    
    logfire.info(
        "Website scrape completed",
        url=url,
        total_words=len(words),
        chunk_count=len(chunks),
        avg_chunk_size_words=avg_chunk_size,
        min_chunk_size_words=min(chunk_sizes) if chunk_sizes else 0,
        max_chunk_size_words=max(chunk_sizes) if chunk_sizes else 0,
        content_hash=content_hash,
        parse_time_ms=parse_elapsed * 1000,
        total_time_ms=total_elapsed * 1000,
    )
    
    return chunks
