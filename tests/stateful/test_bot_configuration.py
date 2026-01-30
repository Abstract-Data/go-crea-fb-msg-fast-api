"""Stateful tests for bot configuration operations."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from src.models.config_models import BotConfiguration


class TestBotConfigurationStateful:
    """Test bot configuration state management."""

    def test_config_operations_basic(self):
        """Basic test of configuration operations."""
        active_configs = {}
        deleted_configs = set()

        # Create a config
        now = datetime.utcnow()
        config1 = BotConfiguration(
            id="bot-1",
            page_id="page-1",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="professional",
            created_at=now,
            updated_at=now,
            is_active=True,
        )
        active_configs["page-1"] = config1
        assert config1.page_id == "page-1"

        # Update tone
        updated_config = BotConfiguration(
            id=config1.id,
            page_id=config1.page_id,
            website_url=config1.website_url,
            reference_doc_id=config1.reference_doc_id,
            tone="friendly",
            created_at=config1.created_at,
            updated_at=datetime.utcnow(),
            is_active=config1.is_active,
        )
        active_configs["page-1"] = updated_config
        assert updated_config.tone == "friendly"
        assert updated_config.tone != config1.tone

        # Verify invariants
        # No duplicate page_ids
        page_ids = [c.page_id for c in active_configs.values()]
        assert len(page_ids) == len(set(page_ids))

        # All configs valid
        for config in active_configs.values():
            assert len(config.page_id) > 0
            assert len(config.website_url) > 0
            assert config.tone in [
                "professional",
                "friendly",
                "casual",
                "formal",
                "humorous",
            ]

    def test_config_deletion(self):
        """Test configuration deletion."""
        active_configs = {}
        deleted_configs = set()

        # Create config
        now = datetime.utcnow()
        config = BotConfiguration(
            id="bot-1",
            page_id="page-1",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="professional",
            created_at=now,
            updated_at=now,
            is_active=True,
        )
        active_configs["page-1"] = config

        # Delete config
        deleted_configs.add("page-1")
        del active_configs["page-1"]

        # Verify deleted
        assert "page-1" in deleted_configs
        assert "page-1" not in active_configs

        # Verify invariant: deleted configs not in active
        for page_id in deleted_configs:
            assert page_id not in active_configs

    def test_multiple_configs(self):
        """Test managing multiple configurations."""
        active_configs = {}

        # Create multiple configs
        for i in range(5):
            now = datetime.utcnow()
            config = BotConfiguration(
                id=f"bot-{i}",
                page_id=f"page-{i}",
                website_url=f"https://example{i}.com",
                reference_doc_id=f"doc-{i}",
                tone="professional",
                created_at=now,
                updated_at=now,
                is_active=True,
            )
            active_configs[f"page-{i}"] = config

        # Verify all configs exist
        assert len(active_configs) == 5

        # Verify no duplicates
        page_ids = [c.page_id for c in active_configs.values()]
        assert len(page_ids) == len(set(page_ids))
