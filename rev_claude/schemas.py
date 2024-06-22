from pydantic import BaseModel, Field
from typing import Union, List, Dict
from enum import Enum


class APIKeyType(Enum):
    PLUS = "plus"
    BASIC = "basic"


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
    files: Union[List[str], None] = None
    need_web_search: bool = False


class FileConversionRequest(BaseModel):
    client_idx: int
    client_type: str


class CreateAPIKeyRequest(BaseModel):
    expiration_days: int = Field(default=1, description="多少天后过期, 默认1天")
    key_type: str = Field(default="plus", description="API key 类型")
    key_number: int = Field(default=1, description="生成多少个key，默认1个")
