"""Integration tests for agent service with Copilot service."""

import pytest

# CopilotService has been removed - functionality migrated to PydanticAI Gateway
# These tests are skipped as they test deprecated functionality
pytestmark = pytest.mark.skip(reason="CopilotService removed - migrated to PydanticAI Gateway")


class TestAgentCopilotIntegration:
    """Test agent service integration with Copilot service."""
    pass
