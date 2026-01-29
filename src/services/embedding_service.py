"""Embedding generation via PydanticAI Gateway."""

from typing import List

import logfire
from pydantic_ai import Embedder

from src.config import get_settings


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts via PydanticAI Gateway.

    Uses settings.embedding_model (e.g. gateway/openai:text-embedding-3-small)
    routed through existing pydantic_ai_gateway_api_key.

    Args:
        texts: List of strings to embed (e.g. chunk contents).

    Returns:
        List of embedding vectors (each a list of floats).
    """
    if not texts:
        return []
    settings = get_settings()
    embedder = Embedder(settings.embedding_model)
    with logfire.span("embedding_generate", text_count=len(texts)):
        result = await embedder.embed_documents(texts)
    return list(result.embeddings)


async def embed_query(query: str) -> List[float]:
    """
    Generate a single embedding for a search query via PydanticAI Gateway.

    Use for query-side embedding when performing similarity search.

    Args:
        query: Search query string.

    Returns:
        Single embedding vector (list of floats).
    """
    if not query or not query.strip():
        return []
    settings = get_settings()
    embedder = Embedder(settings.embedding_model)
    with logfire.span("embedding_query"):
        result = await embedder.embed_query(query)
    if not result.embeddings:
        return []
    return list(result.embeddings[0])
