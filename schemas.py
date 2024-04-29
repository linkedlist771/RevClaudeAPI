from pydantic import BaseModel
from typing import Union, List, Dict



class BaseChatRequest(BaseModel):
    """Base class for chat request models."""

    message: str
    model: str


class ClaudeChatRequest(BaseChatRequest):
    """Request message data model for Claude."""

    stream: bool = True
    conversation_id: Union[str, None] = None
    client_idx: int = 0
    client_type: str
    attachments: Union[List[Dict], None] = None


class FileConversionRequest(BaseModel):
    client_idx: int
    client_type: str
