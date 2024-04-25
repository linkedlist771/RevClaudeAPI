from pydantic import BaseModel
from typing import Union
from fastapi import UploadFile


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


class FileConversionRequest(BaseModel):
    client_idx: int
    client_type: str
    file: UploadFile  # 新增上传文件的字段



