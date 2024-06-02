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


class Message(BaseModel):
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

        if request.conversation_type.value == "normal":
            return f"conversation_history-{request.api_key}-{request.client_idx}-basic"
        return f"conversation_history-{request.api_key}-{request.client_idx}-{request.conversation_type.value}"

    def push_message(
        self, request: ConversationHistoryRequestInput, messages: list[Message]
    ):
        conversation_history_key = self.get_conversation_history_key(request)
        conversation_history_data = self.redis.hget(
            conversation_history_key, request.conversation_id
        )

        if conversation_history_data:
            conversation_history = ConversationHistory.model_validate_json(
                conversation_history_data
            )
            conversation_history.messages.extend(messages)
        else:
            conversation_history = ConversationHistory(
                conversation_id=request.conversation_id,
                messages=messages,
                model=request.model,
            )

        self.redis.hset(
            conversation_history_key,
            request.conversation_id,
            conversation_history.model_dump_json(),
        )

    def get_conversation_histories(
        self, request: ConversationHistoryRequestInput
    ) -> List[ConversationHistory]:
        conversation_history_key = self.get_conversation_history_key(request)
        conversation_histories_data = self.redis.hgetall(conversation_history_key)
        histories = []

        for conversation_id, history_data in conversation_histories_data.items():
            history = ConversationHistory.model_validate_json(history_data)
            histories.append(history)

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
        model=ClaudeModels.CLAUDE,
    )
