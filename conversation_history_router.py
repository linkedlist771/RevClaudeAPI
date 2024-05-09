from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from conversation_history_manager import ConversationHistoryManager, ConversationHistoryRequestInput, ConversationHistory, Message, conversation_history_manager
from models import ClaudeModels

router = APIRouter()

def get_conversation_history_manager():
    return ConversationHistoryManager()

@router.post("/push_message")
async def push_message(
    request: ConversationHistoryRequestInput,
    messages: List[Message],
    ):
    """Push a message to conversation history."""
    conversation_history_manager.push_message(request, messages)
    return {"message": "Message pushed successfully"}

@router.post("/get_conversation_histories")
async def get_conversation_histories(
    request: ConversationHistoryRequestInput,
    ) -> List[ConversationHistory]:
    """Get conversation histories."""
    histories = conversation_history_manager.get_conversation_histories(request)
    return histories

