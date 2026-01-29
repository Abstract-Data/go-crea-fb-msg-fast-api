"""Property-based tests for Pydantic models."""

import pytest
from hypothesis import given, strategies as st, assume
from datetime import datetime

from src.models.messenger import (
    MessengerEntry,
    MessengerMessageIn,
    MessengerWebhookPayload
)
from src.models.agent_models import AgentContext, AgentResponse
from src.models.config_models import (
    WebsiteInput,
    TonePreference,
    FacebookConfig,
    BotConfiguration
)


# Custom URL strategy since Hypothesis doesn't have st.urls()
def url_strategy():
    """Generate valid URL strings."""
    return st.builds(
        lambda scheme, domain, path: f"{scheme}://{domain}.com/{path}",
        scheme=st.sampled_from(["http", "https"]),
        domain=st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
            min_size=3,
            max_size=20
        ),
        path=st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_/"),
            min_size=0,
            max_size=50
        )
    )


class TestMessengerModels:
    """Test Facebook Messenger models."""
    
    @given(
        entry_id=st.text(min_size=1, max_size=100),
        time=st.integers(min_value=0)
    )
    def test_messenger_entry_properties(self, entry_id: str, time: int):
        """Property: MessengerEntry should accept valid inputs."""
        entry = MessengerEntry(id=entry_id, time=time)
        assert entry.id == entry_id
        assert entry.time == time
    
    @given(
        sender_id=st.text(min_size=1, max_size=100),
        recipient_id=st.text(min_size=1, max_size=100),
        text=st.one_of(st.text(max_size=1000), st.none()),
        timestamp=st.integers(min_value=0)
    )
    def test_messenger_message_in_properties(
        self,
        sender_id: str,
        recipient_id: str,
        text: str | None,
        timestamp: int
    ):
        """Property: MessengerMessageIn should accept valid inputs."""
        message = MessengerMessageIn(
            sender_id=sender_id,
            recipient_id=recipient_id,
            text=text,
            timestamp=timestamp
        )
        assert message.sender_id == sender_id
        assert message.recipient_id == recipient_id
        assert message.text == text
        assert message.timestamp == timestamp
    
    def test_messenger_message_in_empty_text(self):
        """Test that empty text is allowed."""
        message = MessengerMessageIn(
            sender_id="sender-123",
            recipient_id="recipient-123",
            text=None,
            timestamp=1234567890
        )
        assert message.text is None
    
    @given(
        object_type=st.text(min_size=1, max_size=50),
        entry_count=st.integers(min_value=0, max_value=10)
    )
    def test_messenger_webhook_payload_properties(
        self,
        object_type: str,
        entry_count: int
    ):
        """Property: MessengerWebhookPayload should accept valid inputs."""
        entries = [
            {"id": f"entry-{i}", "time": 1234567890 + i}
            for i in range(entry_count)
        ]
        payload = MessengerWebhookPayload(
            object=object_type,
            entry=entries
        )
        assert payload.object == object_type
        assert len(payload.entry) == entry_count


class TestAgentModels:
    """Test agent models."""
    
    @given(
        bot_config_id=st.text(min_size=1, max_size=100),
        reference_doc=st.text(min_size=10, max_size=50000),
        tone=st.sampled_from(["professional", "friendly", "casual", "formal", "humorous"]),
        recent_messages=st.lists(st.text(min_size=1, max_size=500), max_size=10)
    )
    def test_agent_context_properties(
        self,
        bot_config_id: str,
        reference_doc: str,
        tone: str,
        recent_messages: list[str]
    ):
        """Property: AgentContext should maintain invariants."""
        context = AgentContext(
            bot_config_id=bot_config_id,
            reference_doc=reference_doc,
            tone=tone,
            recent_messages=recent_messages
        )
        assert context.bot_config_id == bot_config_id
        assert len(context.reference_doc) > 0
        assert context.tone in ["professional", "friendly", "casual", "formal", "humorous"]
        assert isinstance(context.recent_messages, list)
        assert len(context.recent_messages) == len(recent_messages)
    
    @given(
        message=st.text(min_size=1, max_size=300),
        confidence=st.floats(min_value=0.0, max_value=1.0),
        requires_escalation=st.booleans(),
        escalation_reason=st.one_of(st.text(max_size=200), st.none())
    )
    def test_agent_response_properties(
        self,
        message: str,
        confidence: float,
        requires_escalation: bool,
        escalation_reason: str | None
    ):
        """Property: AgentResponse should maintain invariants."""
        response = AgentResponse(
            message=message,
            confidence=confidence,
            requires_escalation=requires_escalation,
            escalation_reason=escalation_reason
        )
        assert response.message == message
        assert 0.0 <= response.confidence <= 1.0
        assert response.requires_escalation == requires_escalation
        assert response.escalation_reason == escalation_reason
    
    def test_agent_response_confidence_bounds(self):
        """Test that confidence is bounded between 0.0 and 1.0."""
        # Valid confidence
        response = AgentResponse(
            message="Test",
            confidence=0.5
        )
        assert 0.0 <= response.confidence <= 1.0
        
        # Test boundary values
        response_min = AgentResponse(message="Test", confidence=0.0)
        response_max = AgentResponse(message="Test", confidence=1.0)
        assert response_min.confidence == 0.0
        assert response_max.confidence == 1.0
    
    def test_agent_response_escalation_logic(self):
        """Test escalation logic."""
        # Escalation required
        response = AgentResponse(
            message="I don't know",
            confidence=0.3,
            requires_escalation=True,
            escalation_reason="Low confidence"
        )
        assert response.requires_escalation is True
        assert response.escalation_reason is not None
        
        # No escalation
        response = AgentResponse(
            message="I can help with that",
            confidence=0.9,
            requires_escalation=False
        )
        assert response.requires_escalation is False


class TestConfigModels:
    """Test configuration models."""
    
    @given(url=url_strategy())
    def test_website_input_properties(self, url: str):
        """Property: WebsiteInput should accept valid URLs."""
        website = WebsiteInput(url=url)
        assert website.url == url
        assert website.url.startswith(("http://", "https://"))
    
    @given(
        tone=st.sampled_from(["professional", "friendly", "casual", "formal", "humorous"]),
        description=st.one_of(st.text(max_size=500), st.none())
    )
    def test_tone_preference_properties(self, tone: str, description: str | None):
        """Property: TonePreference should accept valid tones."""
        preference = TonePreference(tone=tone, description=description)
        assert preference.tone == tone
        assert preference.description == description
    
    @given(
        page_id=st.text(min_size=1, max_size=100),
        page_access_token=st.text(min_size=1, max_size=500),
        verify_token=st.text(min_size=1, max_size=200)
    )
    def test_facebook_config_properties(
        self,
        page_id: str,
        page_access_token: str,
        verify_token: str
    ):
        """Property: FacebookConfig should accept valid inputs."""
        config = FacebookConfig(
            page_id=page_id,
            page_access_token=page_access_token,
            verify_token=verify_token
        )
        assert config.page_id == page_id
        assert config.page_access_token == page_access_token
        assert config.verify_token == verify_token
    
    @given(
        page_id=st.text(min_size=1, max_size=100),
        website_url=url_strategy(),
        reference_doc_id=st.uuids(),
        tone=st.sampled_from(["professional", "friendly", "casual", "formal", "humorous"]),
        is_active=st.booleans()
    )
    def test_bot_configuration_properties(
        self,
        page_id: str,
        website_url: str,
        reference_doc_id,
        tone: str,
        is_active: bool
    ):
        """Property: BotConfiguration should maintain invariants."""
        now = datetime.utcnow()
        config = BotConfiguration(
            id=str(reference_doc_id),  # Using UUID as string
            page_id=page_id,
            website_url=website_url,
            reference_doc_id=str(reference_doc_id),
            tone=tone,
            created_at=now,
            updated_at=now,
            is_active=is_active
        )
        assert config.page_id == page_id
        assert config.website_url == website_url
        assert config.tone in ["professional", "friendly", "casual", "formal", "humorous"]
        assert config.is_active == is_active
        assert isinstance(config.created_at, datetime)
        assert isinstance(config.updated_at, datetime)
    
    def test_bot_configuration_datetime_handling(self):
        """Test datetime handling in BotConfiguration."""
        now = datetime.utcnow()
        config = BotConfiguration(
            page_id="page-123",
            website_url="https://example.com",
            reference_doc_id="doc-123",
            tone="professional",
            created_at=now,
            updated_at=now
        )
        assert config.created_at == now
        assert config.updated_at == now
        assert isinstance(config.created_at, datetime)
        assert isinstance(config.updated_at, datetime)
