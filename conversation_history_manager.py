import redis
import uuid
from enum import Enum
from typing import Union, Tuple, List, Optional
from loguru import logger
from pydantic import BaseModel
from api_key_manage import APIKeyType
from claude import Client
from tqdm import tqdm

from claude_cookie_manage import CookieKeyType
from models import ClaudeModels



class RoleType(Enum):
    ASSISTANT = "assistant"
    USER = "user"


class  Message(BaseModel):
    content: str
    role: RoleType

class ConversationHistory(BaseModel):
    conversation_id: str
    messages: List[Message]
    model: ClaudeModels

class ConversationHistoryRequestInput(BaseModel):
    client_idx: int
    conversation_type: CookieKeyType
    api_key: str
    conversation_id: Optional[str] = None
    model: Optional[ClaudeModels] = None


class ConversationHistoryManager:

    def __init__(self, host="localhost", port=6379, db=0):
        """Initialize the connection to Redis."""
        self.redis = redis.StrictRedis(host=host, port=port, db=db)


    def get_conversation_history_key(self, request: ConversationHistoryRequestInput):
        return f"conversation_history-{request.api_key}-{request.client_idx}-{request.conversation_type.value}"

    def push_message(self, request: ConversationHistoryRequestInput, messages: list[Message]):
        conversation_history_key = self.get_conversation_history_key(request)
        conversation_histories = self.redis.lrange(conversation_history_key, 0, -1)
        conversation_history = None
        for history in conversation_histories:
            history_data = ConversationHistory.model_validate_json(history)
            if history_data.conversation_id == request.conversation_id:
                conversation_history = history_data
                break
        if conversation_history:
            # 如果对话历史存在,添加消息
            conversation_history.messages.extend(messages)
            self.redis.lrem(conversation_history_key, 1, conversation_history.json())
            self.redis.rpush(conversation_history_key, conversation_history.json())
        else:
            # 如果对话历史不存在,创建新的对话历史并添加消息
            new_conversation_history = ConversationHistory(
                conversation_id=request.conversation_id,
                messages=messages,
                model=request.model
            )
            self.redis.rpush(conversation_history_key, new_conversation_history.json())

    def get_conversation_histories(self, request: ConversationHistoryRequestInput) -> List[ConversationHistory]:
        conversation_history_key = self.get_conversation_history_key(request)
        conversation_histories = self.redis.lrange(conversation_history_key, 0, -1)
        histories = []
        for history in conversation_histories:
            history_data = ConversationHistory.model_validate_json(history)
            histories.append(history_data)
        return histories

    def delete_all_conversations(self, request: ConversationHistoryRequestInput):
        conversation_history_key = self.get_conversation_history_key(request)
        self.redis.delete(conversation_history_key)


def get_conversation_history_manager():
    return ConversationHistoryManager()


conversation_history_manager = ConversationHistoryManager()



# Example usage of the APIKeyManager
if __name__ == "__main__":
    manager = ConversationHistoryManager()
    request = ConversationHistoryRequestInput(
        client_idx=0,
        conversation_type=CookieKeyType.BASIC,
        api_key="sj-6d3f5d6",
        conversation_id="123",
        model=ClaudeModels.CLAUDE
    )
