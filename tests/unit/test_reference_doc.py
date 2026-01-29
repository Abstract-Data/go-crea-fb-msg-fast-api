"""Tests for reference document service."""

import pytest
import hashlib
from hypothesis import given, strategies as st
from unittest.mock import AsyncMock

from src.services.reference_doc import build_reference_doc
from src.services.copilot_service import CopilotService


class TestBuildReferenceDoc:
    """Test build_reference_doc() function."""
    
    @pytest.mark.asyncio
    async def test_build_reference_doc_valid_inputs(self, mock_copilot_service):
        """Test build_reference_doc() with valid inputs."""
        mock_copilot_service.synthesize_reference.return_value = "# Reference Document\n\nTest content"
        
        markdown_content, content_hash = await build_reference_doc(
            copilot=mock_copilot_service,
            website_url="https://example.com",
            text_chunks=["chunk1", "chunk2"]
        )
        
        assert isinstance(markdown_content, str)
        assert len(markdown_content) > 0
        assert isinstance(content_hash, str)
        assert len(content_hash) == 64  # SHA256 produces 64-character hex string
    
    @pytest.mark.asyncio
    async def test_build_reference_doc_calls_copilot(self, mock_copilot_service):
        """Test that build_reference_doc() calls Copilot service."""
        mock_copilot_service.synthesize_reference.return_value = "# Test Document"
        
        await build_reference_doc(
            copilot=mock_copilot_service,
            website_url="https://example.com",
            text_chunks=["chunk1", "chunk2", "chunk3"]
        )
        
        mock_copilot_service.synthesize_reference.assert_called_once_with(
            "https://example.com",
            ["chunk1", "chunk2", "chunk3"]
        )
    
    @given(content=st.text(min_size=1, max_size=10000))
    def test_content_hash_determinism(self, content: str):
        """Property: Content hash should be deterministic (same input = same hash)."""
        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()
        
        # Same content should produce same hash
        assert hash1 == hash2
    
    @given(
        content1=st.text(min_size=1, max_size=10000),
        content2=st.text(min_size=1, max_size=10000)
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
    async def test_content_hash_format(self, mock_copilot_service):
        """Test that content hash is in correct format (SHA256 hex)."""
        mock_copilot_service.synthesize_reference.return_value = "Test content"
        
        _, content_hash = await build_reference_doc(
            copilot=mock_copilot_service,
            website_url="https://example.com",
            text_chunks=["chunk1"]
        )
        
        # SHA256 produces 64-character hexadecimal string
        assert len(content_hash) == 64
        assert all(c in "0123456789abcdef" for c in content_hash)
    
    @pytest.mark.asyncio
    async def test_build_reference_doc_properties(self, mock_copilot_service):
        """Test build_reference_doc() returns valid tuple."""
        text_chunks = ["chunk0", "chunk1", "chunk2"]
        mock_copilot_service.synthesize_reference.return_value = "# Test Document"
        
        markdown_content, content_hash = await build_reference_doc(
            copilot=mock_copilot_service,
            website_url="https://example.com",
            text_chunks=text_chunks
        )
        
        # Invariants
        assert isinstance(markdown_content, str)
        assert isinstance(content_hash, str)
        assert len(content_hash) == 64
        assert len(markdown_content) > 0
    
    @pytest.mark.asyncio
    async def test_build_reference_doc_hash_consistency(self, mock_copilot_service):
        """Test that hash is consistent across multiple calls with same content."""
        content = "# Reference Document\n\nThis is test content."
        mock_copilot_service.synthesize_reference.return_value = content
        
        # First call
        _, hash1 = await build_reference_doc(
            copilot=mock_copilot_service,
            website_url="https://example.com",
            text_chunks=["chunk1"]
        )
        
        # Reset and call again with same content
        mock_copilot_service.synthesize_reference.return_value = content
        _, hash2 = await build_reference_doc(
            copilot=mock_copilot_service,
            website_url="https://example.com",
            text_chunks=["chunk1"]
        )
        
        assert hash1 == hash2
    
    @pytest.mark.asyncio
    async def test_build_reference_doc_empty_content(self, mock_copilot_service):
        """Test handling of empty content."""
        mock_copilot_service.synthesize_reference.return_value = ""
        
        markdown_content, content_hash = await build_reference_doc(
            copilot=mock_copilot_service,
            website_url="https://example.com",
            text_chunks=["chunk1"]
        )
        
        assert markdown_content == ""
        # Empty string should still produce a valid hash
        assert len(content_hash) == 64
    
    @pytest.mark.asyncio
    async def test_build_reference_doc_unicode_content(self, mock_copilot_service):
        """Test handling of unicode content."""
        unicode_content = "# 参考文档\n\n这是测试内容。🎉"
        mock_copilot_service.synthesize_reference.return_value = unicode_content
        
        markdown_content, content_hash = await build_reference_doc(
            copilot=mock_copilot_service,
            website_url="https://example.com",
            text_chunks=["chunk1"]
        )
        
        assert markdown_content == unicode_content
        assert len(content_hash) == 64
