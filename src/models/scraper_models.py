"""Models for scraper results: per-page data and scrape result."""

from dataclasses import dataclass
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


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


class ScrapedPageCreate(BaseModel):
    """Parameters for creating a scraped page record.

    Replaces the long parameter list in create_scraped_page() with a
    single type-safe parameter object.
    """

    reference_doc_id: str = Field(..., description="Reference document UUID")
    url: str = Field(..., description="Original page URL")
    normalized_url: str = Field(..., description="Normalized URL for deduplication")
    title: str = Field(default="", description="Page title")
    raw_content: str = Field(..., description="Scraped text content")
    word_count: int = Field(..., ge=0, description="Word count of content")
    scraped_at: datetime = Field(..., description="Timestamp when page was scraped")
