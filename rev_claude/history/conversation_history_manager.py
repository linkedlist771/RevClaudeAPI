from datetime import datetime

import redis
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from rev_claude.configs import REDIS_HOST, REDIS_PORT
from rev_claude.cookie.claude_cookie_manage import CookieKeyType
from rev_claude.models import ClaudeModels
from rev_claude.utils.time_zone_utils import get_shanghai_time


class RoleType(Enum):
    ASSISTANT = "assistant"
    USER = "user"


class Message(BaseModel):
    content: str
    role: RoleType
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


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

    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, db=0):
        """Initialize the connection to Redis."""
        self.redis = redis.StrictRedis(host=host, port=port, db=db)

    def get_conversation_history_key(self, request: ConversationHistoryRequestInput):

        if request.conversation_type.value == "normal":
            return f"conversation_history-{request.api_key}-{request.client_idx}-basic"
        return f"conversation_history-{request.api_key}-{request.client_idx}-{request.conversation_type.value}"

    # def push_message(
    #     self, request: ConversationHistoryRequestInput, messages: list[Message]
    # ):
    #     conversation_history_key = self.get_conversation_history_key(request)
    #     conversation_history_data = self.redis.hget(
    #         conversation_history_key, request.conversation_id
    #     )
    #
    #     if conversation_history_data:
    #         conversation_history = ConversationHistory.model_validate_json(
    #             conversation_history_data
    #         )
    #         conversation_history.messages.extend(messages)
    #     else:
    #         conversation_history = ConversationHistory(
    #             conversation_id=request.conversation_id,
    #             messages=messages,
    #             model=request.model,
    #         )
    #
    #     self.redis.hset(
    #         conversation_history_key,
    #         request.conversation_id,
    #         conversation_history.model_dump_json(),
    #     )
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
            # 确保所有消息都有时间戳
            for message in messages:
                if message.timestamp is None:
                    message.timestamp = get_shanghai_time()
            conversation_history.messages.extend(messages)
        else:
            # 确保所有消息都有时间戳
            for message in messages:
                if message.timestamp is None:
                    message.timestamp = get_shanghai_time()
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

    # def get_conversation_histories(
    #     self, request: ConversationHistoryRequestInput
    # ) -> List[ConversationHistory]:
    #     conversation_history_key = self.get_conversation_history_key(request)
    #     conversation_histories_data = self.redis.hgetall(conversation_history_key)
    #     histories = []
    #
    #     for conversation_id, history_data in conversation_histories_data.items():
    #         history = ConversationHistory.model_validate_json(history_data)
    #         histories.append(history)
    #
    #     return histories
    def get_conversation_histories(
            self, request: ConversationHistoryRequestInput
    ) -> List[ConversationHistory]:
        conversation_history_key = self.get_conversation_history_key(request)
        conversation_histories_data = self.redis.hgetall(conversation_history_key)
        histories = []

        for conversation_id, history_data in conversation_histories_data.items():
            history = ConversationHistory.model_validate_json(history_data)

            # 处理可能缺失的时间戳， 如果没有的话， 就返回初始时间戳, 就是刚开始的哪个1970年， 但是单位要和datetime.utcnow()一样

            default_time = datetime(1970, 1, 1)
            for message in history.messages:
                if message.timestamp is None:
                    message.timestamp = default_time
                    default_time = default_time.replace(microsecond=default_time.microsecond + 1)
            histories.append(history)
        histories.sort(key=lambda h: h.messages[-1].timestamp if h.messages else datetime.min)

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
