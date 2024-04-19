from pydantic import BaseModel


class BaseChatRequest(BaseModel):
    """Base class for chat request models."""
    message: str
    model: str


class ClaudeChatRequest(BaseChatRequest):
    """Request message data model for Claude."""
    stream: bool = True
    conversation_id: str
