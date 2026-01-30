"""Tests for reference document service."""

import pytest
import hashlib
from hypothesis import given, strategies as st
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.reference_doc import build_reference_document, ReferenceDocument


class TestBuildReferenceDocument:
    """Test build_reference_document() function."""

    @pytest.mark.asyncio
    async def test_build_reference_document_valid_inputs(self):
        """Test build_reference_document() with valid inputs."""
        mock_doc = ReferenceDocument(
            overview="Test overview",
            key_topics=["Topic 1", "Topic 2"],
            common_questions=["Q1", "Q2"],
            important_details="Important info",
            contact_info="contact@example.com",
        )

        mock_result = MagicMock()
        mock_result.output = mock_doc

        mock_settings = MagicMock()
        mock_settings.default_model = "openai:gpt-4o-mini"
        with (
            patch(
                "src.services.reference_doc.get_settings", return_value=mock_settings
            ),
            patch("src.services.reference_doc.Agent") as mock_agent_class,
        ):
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            markdown_content = await build_reference_document(
                website_url="https://example.com", text_chunks=["chunk1", "chunk2"]
            )

            assert isinstance(markdown_content, str)
            assert len(markdown_content) > 0
            assert "example.com" in markdown_content
            assert "Test overview" in markdown_content

    @pytest.mark.asyncio
    async def test_build_reference_document_calls_agent(self):
        """Test that build_reference_document() calls PydanticAI agent."""
        mock_doc = ReferenceDocument(
            overview="Overview",
            key_topics=["Topic"],
            common_questions=["Q"],
            important_details="Details",
            contact_info=None,
        )

        mock_result = MagicMock()
        mock_result.output = mock_doc

        mock_settings = MagicMock()
        mock_settings.default_model = "openai:gpt-4o-mini"
        with (
            patch(
                "src.services.reference_doc.get_settings", return_value=mock_settings
            ),
            patch("src.services.reference_doc.Agent") as mock_agent_class,
        ):
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            await build_reference_document(
                website_url="https://example.com",
                text_chunks=["chunk1", "chunk2", "chunk3"],
            )

            # Verify agent.run was called
            mock_agent_instance.run.assert_called_once()
            call_args = mock_agent_instance.run.call_args
            assert call_args is not None
            # Check that the prompt includes website URL and chunks
            prompt = call_args[0][0]
            assert "example.com" in prompt
            assert "chunk1" in prompt

    @given(content=st.text(min_size=1, max_size=10000))
    def test_content_hash_determinism(self, content: str):
        """Property: Content hash should be deterministic (same input = same hash)."""
        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()

        # Same content should produce same hash
        assert hash1 == hash2

    @given(
        content1=st.text(min_size=1, max_size=10000),
        content2=st.text(min_size=1, max_size=10000),
    )
    def test_content_hash_uniqueness(self, content1: str, content2: str):
        """Property: Different content should produce different hashes."""
        # Skip if content is the same
        if content1 == content2:
            return

        hash1 = hashlib.sha256(content1.encode()).hexdigest()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()

        # Different content should produce different hash
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_build_reference_document_properties(self):
        """Test build_reference_document() returns valid markdown."""
        mock_doc = ReferenceDocument(
            overview="Overview",
            key_topics=["Topic 1", "Topic 2"],
            common_questions=["Q1"],
            important_details="Details",
            contact_info="contact@example.com",
        )

        mock_result = MagicMock()
        mock_result.output = mock_doc

        mock_settings = MagicMock()
        mock_settings.default_model = "openai:gpt-4o-mini"
        with (
            patch(
                "src.services.reference_doc.get_settings", return_value=mock_settings
            ),
            patch("src.services.reference_doc.Agent") as mock_agent_class,
        ):
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            text_chunks = ["chunk0", "chunk1", "chunk2"]
            markdown_content = await build_reference_document(
                website_url="https://example.com", text_chunks=text_chunks
            )

            # Invariants
            assert isinstance(markdown_content, str)
            assert len(markdown_content) > 0
            # Check markdown structure
            assert "# Reference Document" in markdown_content
            assert "## Overview" in markdown_content
            assert "## Key Topics" in markdown_content

    @pytest.mark.asyncio
    async def test_build_reference_document_with_empty_chunks(self):
        """Test handling of empty chunks."""
        mock_doc = ReferenceDocument(
            overview="Overview",
            key_topics=[],
            common_questions=[],
            important_details="",
            contact_info=None,
        )

        mock_result = MagicMock()
        mock_result.output = mock_doc

        mock_settings = MagicMock()
        mock_settings.default_model = "openai:gpt-4o-mini"
        with (
            patch(
                "src.services.reference_doc.get_settings", return_value=mock_settings
            ),
            patch("src.services.reference_doc.Agent") as mock_agent_class,
        ):
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            markdown_content = await build_reference_document(
                website_url="https://example.com", text_chunks=[]
            )

            assert isinstance(markdown_content, str)
            assert "example.com" in markdown_content

    @pytest.mark.asyncio
    async def test_build_reference_document_unicode_content(self):
        """Test handling of unicode content."""
        mock_doc = ReferenceDocument(
            overview="概述",
            key_topics=["主题1", "主题2"],
            common_questions=["问题1"],
            important_details="重要信息🎉",
            contact_info="联系@example.com",
        )

        mock_result = MagicMock()
        mock_result.output = mock_doc

        mock_settings = MagicMock()
        mock_settings.default_model = "openai:gpt-4o-mini"
        with (
            patch(
                "src.services.reference_doc.get_settings", return_value=mock_settings
            ),
            patch("src.services.reference_doc.Agent") as mock_agent_class,
        ):
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_result)
            mock_agent_class.return_value = mock_agent_instance

            markdown_content = await build_reference_document(
                website_url="https://example.com", text_chunks=["chunk1"]
            )

            assert isinstance(markdown_content, str)
            assert "概述" in markdown_content
            assert "🎉" in markdown_content
