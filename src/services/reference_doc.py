"""Reference document builder using PydanticAI Gateway."""

import hashlib
import logging
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.config import get_settings
from src.db.repository import create_reference_document

logger = logging.getLogger(__name__)


class ReferenceDocument(BaseModel):
    """Structured reference document output."""
    overview: str = Field(..., description="Brief overview of the website/organization")
    key_topics: list[str] = Field(..., description="Main topics covered")
    common_questions: list[str] = Field(..., description="Anticipated FAQs")
    important_details: str = Field(..., description="Critical information to remember")
    detailed_content: str = Field(
        "",
        description="Comprehensive section with specific names, endorsers, policies, quotes, contact details. Include as much specific detail as the source provides—do not summarize into vague bullet points.",
    )
    contact_info: str | None = Field(None, description="Contact information if available")


async def build_reference_document(
    website_url: str,
    text_chunks: list[str],
) -> str:
    """
    Build a reference document from scraped website content.
    
    Args:
        website_url: Source website URL
        text_chunks: List of text chunks from scraping
        
    Returns:
        Synthesized markdown reference document
    """
    settings = get_settings()
    
    # Create synthesis agent
    agent = Agent(
        settings.default_model,
        output_type=ReferenceDocument,
        system_prompt="""You are a content synthesis assistant.
Your job is to create comprehensive reference documents for AI agents that will answer questions about websites.
Include specific details: names, policies, endorsements, quotes, dates, and concrete facts from the content.
Do not summarize into vague bullet points—preserve enough detail so the agent can answer "Who endorses X?", "What is their position on Y?", and similar questions accurately.
Focus on: policies, services, FAQs, contact information, key positions, and any lists (endorsements, team, issues).""",
    )

    # Build prompt with all chunks (content from multiple pages)
    chunks_text = "\n\n---\n\n".join(
        f"CHUNK {i+1}:\n{chunk}"
        for i, chunk in enumerate(text_chunks)
    )

    prompt = f"""Analyze the following content from {website_url} (may include multiple pages). Create a structured reference document.

WEBSITE CONTENT (all crawled pages):
{chunks_text}

Create a comprehensive reference document that an AI agent can use to answer detailed questions.
- In overview, key_topics, important_details: be specific (names, policies, endorsements, facts).
- In detailed_content: include extensive detail—list endorsers by name where given, quote key positions, include contact info (phone, email, address if present), policies with specifics. Do not summarize into vague bullet points; preserve as much of the source detail as fits."""
    
    # Run synthesis
    result = await agent.run(prompt)
    doc = result.output
    
    # Convert to markdown
    markdown = f"""# Reference Document: {website_url}

## Overview
{doc.overview}

## Key Topics
{chr(10).join(f"- {topic}" for topic in doc.key_topics)}

## Common Questions
{chr(10).join(f"- {q}" for q in doc.common_questions)}

## Important Details
{doc.important_details}

## Detailed Content
{doc.detailed_content or "(No additional detail extracted)"}

## Contact Information
{doc.contact_info or "Not available"}
"""

    return markdown


async def create_and_store_reference_document(
    website_url: str,
    text_chunks: list[str],
) -> str:
    """
    Create reference document and store in database.
    
    Returns:
        Reference document ID
    """
    # Build document
    content = await build_reference_document(website_url, text_chunks)
    
    # Calculate hash
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    
    # Store in database
    doc_id = create_reference_document(
        content=content,
        source_url=website_url,
        content_hash=content_hash,
    )
    
    logger.info(f"Created reference document: {doc_id}")
    return doc_id
