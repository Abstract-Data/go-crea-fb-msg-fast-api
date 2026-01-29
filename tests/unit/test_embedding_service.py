"""Tests for embedding service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.embedding_service import generate_embeddings, embed_query


class TestGenerateEmbeddings:
    """Test generate_embeddings()."""

    @pytest.mark.asyncio
    async def test_generate_embeddings_empty_list(self):
        """Empty input returns empty list."""
        result = await generate_embeddings([])
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_embeddings_returns_vectors(self):
        """generate_embeddings returns list of vectors (list of floats)."""
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1] * 1536, [0.2] * 1536]
        with patch(
            "src.services.embedding_service.Embedder"
        ) as mock_embedder_class:
            mock_embedder = MagicMock()
            mock_embedder.embed_documents = AsyncMock(return_value=mock_result)
            mock_embedder_class.return_value = mock_embedder
            result = await generate_embeddings(["text one", "text two"])
        assert len(result) == 2
        assert len(result[0]) == 1536
        assert len(result[1]) == 1536
        assert result[0][0] == 0.1
        assert result[1][0] == 0.2

    @pytest.mark.asyncio
    async def test_generate_embeddings_calls_embed_documents(self):
        """generate_embeddings calls Embedder with settings.embedding_model."""
        mock_result = MagicMock()
        mock_result.embeddings = [[0.0] * 1536]
        mock_settings = MagicMock()
        mock_settings.embedding_model = "gateway/openai:text-embedding-3-small"
        with (
            patch("src.services.embedding_service.get_settings", return_value=mock_settings),
            patch("src.services.embedding_service.Embedder") as mock_embedder_class,
        ):
            mock_embedder = MagicMock()
            mock_embedder.embed_documents = AsyncMock(return_value=mock_result)
            mock_embedder_class.return_value = mock_embedder
            await generate_embeddings(["hello"])
        mock_embedder_class.assert_called_once_with("gateway/openai:text-embedding-3-small")
        mock_embedder.embed_documents.assert_called_once_with(["hello"])


class TestEmbedQuery:
    """Test embed_query()."""

    @pytest.mark.asyncio
    async def test_embed_query_empty_string_returns_empty(self):
        """Empty or whitespace query returns empty list."""
        result = await embed_query("")
        assert result == []
        result = await embed_query("   ")
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_query_returns_vector(self):
        """embed_query returns a single vector."""
        mock_result = MagicMock()
        mock_result.embeddings = [[0.5] * 1536]
        with patch("src.services.embedding_service.Embedder") as mock_embedder_class:
            mock_embedder = MagicMock()
            mock_embedder.embed_query = AsyncMock(return_value=mock_result)
            mock_embedder_class.return_value = mock_embedder
            result = await embed_query("search query")
        assert len(result) == 1536
        assert result[0] == 0.5

    @pytest.mark.asyncio
    async def test_embed_query_no_embeddings_returns_empty(self):
        """When embed_query returns no embeddings, return empty list."""
        mock_result = MagicMock()
        mock_result.embeddings = []
        with patch("src.services.embedding_service.Embedder") as mock_embedder_class:
            mock_embedder = MagicMock()
            mock_embedder.embed_query = AsyncMock(return_value=mock_result)
            mock_embedder_class.return_value = mock_embedder
            result = await embed_query("query")
        assert result == []
