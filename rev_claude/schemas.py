from enum import Enum
from typing import Dict, List, Union

from pydantic import BaseModel, Field


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
    need_artifacts: bool = False


class ObtainReverseOfficialLoginRouterRequest(BaseModel):
    client_idx: int = 0
    client_type: str


class FileConversionRequest(BaseModel):
    client_idx: int
    client_type: str


class CreateAPIKeyRequest(BaseModel):
    expiration_days: float = Field(default=1.0, description="多少天后过期, 默认1天")
    key_type: str = Field(default="plus", description="API key 类型")
    key_number: int = Field(default=1, description="生成多少个key，默认1个")


class ArtifactsCodeUploadRequest(BaseModel):
    code: str


class BatchAPIKeysDeleteRequest(BaseModel):
    api_keys: List[str]


class ExtendExpirationRequest(BaseModel):
    additional_days: int
