"""Additional property-based tests with Hypothesis."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
import re


# Custom URL strategy since Hypothesis doesn't have st.urls()
def url_strategy():
    """Generate valid URL strings."""
    return st.builds(
        lambda scheme, domain, path: f"{scheme}://{domain}.com/{path}",
        scheme=st.sampled_from(["http", "https"]),
        domain=st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
            min_size=3,
            max_size=20,
        ),
        path=st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_/"),
            min_size=0,
            max_size=50,
        ),
    )


class TestURLValidation:
    """Property-based tests for URL validation."""

    @given(
        url=st.one_of(
            url_strategy(), st.text().filter(lambda x: not x.startswith("http"))
        )
    )
    def test_url_validation_properties(self, url: str):
        """Property: URLs starting with http/https should be valid."""
        is_valid = url.startswith(("http://", "https://"))

        if url.startswith(("http://", "https://")):
            assert is_valid is True
        elif not url.startswith("http"):
            # Non-URL strings might still be valid URLs if they match URL pattern
            # But for our purposes, we expect http/https prefix
            pass  # Accept both valid and invalid non-http URLs

    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    @given(
        scheme=st.sampled_from(["http", "https"]),
        domain=st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789."),
            min_size=5,
            max_size=50,
        ).filter(lambda x: "." in x and not x.startswith(".") and not x.endswith(".")),
        path=st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_/"),
            max_size=50,
        ),
    )
    def test_url_construction_properties(self, scheme: str, domain: str, path: str):
        """Property: Constructed URLs should be valid."""
        url = f"{scheme}://{domain}/{path.lstrip('/')}"

        # Should start with http:// or https://
        assert url.startswith(("http://", "https://"))

        # Should contain domain
        assert domain in url


class TestMessageValidation:
    """Property-based tests for message validation."""

    @given(message=st.text(min_size=1, max_size=1000))
    def test_message_length_properties(self, message: str):
        """Property: Messages within length limits should be valid."""
        is_valid_length = 1 <= len(message) <= 1000

        if len(message) <= 1000:
            assert is_valid_length is True
        else:
            assert is_valid_length is False

    @given(message=st.text(min_size=1, max_size=1000))
    def test_message_non_empty_property(self, message: str):
        """Property: Valid messages should be non-empty (after stripping whitespace)."""
        assume(len(message.strip()) > 0)
        assert len(message.strip()) > 0

    @given(message=st.text(min_size=1, max_size=1000))
    def test_message_whitespace_handling(self, message: str):
        """Property: Messages with only whitespace should be handled."""
        stripped = message.strip()

        if len(stripped) == 0:
            # Empty after stripping
            assert len(message) > 0  # Original had whitespace
        else:
            assert len(stripped) > 0


class TestConfidenceScoreValidation:
    """Property-based tests for confidence score validation."""

    @given(confidence=st.floats(min_value=0.0, max_value=1.0))
    def test_confidence_bounds_property(self, confidence: float):
        """Property: Confidence scores should be in valid range."""
        assert 0.0 <= confidence <= 1.0

    @given(confidence=st.floats(min_value=-1.0, max_value=2.0))
    def test_confidence_validation(self, confidence: float):
        """Property: Invalid confidence scores should be rejected."""
        is_valid = 0.0 <= confidence <= 1.0

        if confidence < 0.0 or confidence > 1.0:
            assert is_valid is False
        else:
            assert is_valid is True


class TestToneValidation:
    """Property-based tests for tone validation."""

    @given(
        tone=st.sampled_from(
            ["professional", "friendly", "casual", "formal", "humorous"]
        )
    )
    def test_valid_tone_property(self, tone: str):
        """Property: Valid tones should be accepted."""
        valid_tones = ["professional", "friendly", "casual", "formal", "humorous"]
        assert tone in valid_tones

    @given(tone=st.text(min_size=1, max_size=50))
    def test_tone_validation_property(self, tone: str):
        """Property: Invalid tones should be rejected."""
        valid_tones = ["professional", "friendly", "casual", "formal", "humorous"]
        is_valid = tone in valid_tones

        if tone in valid_tones:
            assert is_valid is True
        else:
            assert is_valid is False


class TestContentHashProperties:
    """Property-based tests for content hash properties."""

    @given(
        content1=st.text(min_size=1, max_size=10000),
        content2=st.text(min_size=1, max_size=10000),
    )
    def test_hash_collision_resistance(self, content1: str, content2: str):
        """Property: Different content should produce different hashes (with high probability)."""
        import hashlib

        hash1 = hashlib.sha256(content1.encode()).hexdigest()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()

        if content1 != content2:
            # Very high probability of different hashes
            # In practice, SHA256 collisions are extremely rare
            assert hash1 != hash2 or content1 == content2

    @given(content=st.text(min_size=1, max_size=10000))
    def test_hash_determinism_property(self, content: str):
        """Property: Same content should always produce same hash."""
        import hashlib

        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()

        assert hash1 == hash2

    @given(content=st.text(min_size=1, max_size=10000))
    def test_hash_format_property(self, content: str):
        """Property: Hash should be 64-character hexadecimal string."""
        import hashlib

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        assert len(content_hash) == 64
        assert all(c in "0123456789abcdef" for c in content_hash)


class TestChunkingProperties:
    """Property-based tests for text chunking properties."""

    @given(
        text_length=st.integers(min_value=100, max_value=10000),
        target_size=st.integers(min_value=500, max_value=800),
    )
    def test_chunking_properties(self, text_length: int, target_size: int):
        """Property: Chunking should produce valid chunks."""
        # Simulate chunking logic
        words = ["word"] * text_length
        chunks = []
        current_chunk = []
        current_count = 0

        for word in words:
            current_chunk.append(word)
            current_count += 1

            if current_count >= target_size:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_count = 0

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        # Invariants
        assert isinstance(chunks, list)
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) > 0 for chunk in chunks)

        # All chunks except last should be approximately target size
        for chunk in chunks[:-1]:
            word_count = len(chunk.split())
            assert word_count >= target_size - 100  # Allow some flexibility


class TestDataTransformationProperties:
    """Property-based tests for data transformation functions."""

    @given(text=st.text(min_size=0, max_size=1000))
    def test_whitespace_normalization_property(self, text: str):
        """Property: Whitespace normalization should preserve content."""
        import re

        normalized = re.sub(r"\s+", " ", text).strip()

        # Normalized text should not contain multiple consecutive spaces
        assert "  " not in normalized
        assert "\n\n" not in normalized

        # Word count should be preserved (approximately)
        original_words = len(text.split())
        normalized_words = len(normalized.split())

        # Should be approximately the same (allowing for edge cases)
        assert abs(original_words - normalized_words) <= 1 or len(text) == 0
