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
        result_type=ReferenceDocument,
        system_prompt="""You are a content synthesis assistant. 
Your job is to create comprehensive reference documents for AI agents that will answer questions about websites.
Focus on extracting: policies, services, FAQs, contact information, and key positions/statements.
Be thorough but concise.""",
    )
    
    # Build prompt with all chunks
    chunks_text = "\n\n---\n\n".join(
        f"CHUNK {i+1}:\n{chunk}" 
        for i, chunk in enumerate(text_chunks)
    )
    
    prompt = f"""Analyze the following content from {website_url} and create a structured reference document.

WEBSITE CONTENT:
{chunks_text}

Create a comprehensive reference document that an AI agent can use to answer questions about this website."""
    
    # Run synthesis
    result = await agent.run(prompt)
    doc = result.data
    
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
