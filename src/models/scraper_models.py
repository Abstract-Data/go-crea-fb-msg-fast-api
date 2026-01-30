"""Models for scraper results: per-page data and scrape result."""

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class ScrapedPage:
    """Metadata and content for a single scraped page."""

    url: str
    normalized_url: str
    title: str
    content: str
    word_count: int
    scraped_at: datetime


@dataclass
class ScrapeResult:
    """Result of a multi-page scrape: pages and combined chunks."""

    pages: List[ScrapedPage]
    chunks: List[str]
    content_hash: str
