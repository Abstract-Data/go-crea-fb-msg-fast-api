"""Integration tests for scraper and Copilot service."""

import pytest

# CopilotService has been removed - functionality migrated to PydanticAI Gateway
# These tests are skipped as they test deprecated functionality
pytestmark = pytest.mark.skip(
    reason="CopilotService removed - migrated to PydanticAI Gateway"
)


class TestScraperCopilotIntegration:
    """Test scraper → Copilot synthesis flow."""

    pass
