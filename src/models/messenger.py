"""Incoming/outgoing Facebook Messenger models."""

from pydantic import BaseModel


class MessengerEntry(BaseModel):
    """Facebook webhook entry."""
    id: str
    time: int


class MessengerMessageIn(BaseModel):
    """Incoming Facebook Messenger message."""
    sender_id: str
    recipient_id: str
    text: str | None = None
    timestamp: int


class MessengerWebhookPayload(BaseModel):
    """Facebook webhook payload."""
    object: str
    entry: list[dict]  # Can be refined later with specific entry models
