from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from schemas import ClaudeChatRequest
from loguru import logger

from models import ClaudeModels

# This in only for claude router, I do not use the

router = APIRouter()


def obtain_claude_client():
    from main import CLAUDE_CLIENT
    return CLAUDE_CLIENT


@router.get("/list_conversations")
async def list_conversations(claude_client=Depends(obtain_claude_client)):
    return claude_client.list_all_conversations()
    # return {"message": "Hello World"}


@router.get("/list_models")
async def list_models():
    return [model.value for model in ClaudeModels]

import time
def generate_data():
    """生成器函数，每秒输出当前时间戳"""
    for _ in range(20):
        yield f"data: {time.time()}\n\n"
        logger.info(f"data: {time.time()}")
        time.sleep(1)  # 模拟数据处理时间



@router.post("/chat")
async def chat(claude_chat_request: ClaudeChatRequest, claude_client=Depends(obtain_claude_client)):
    """返回一个流式响应，客户端将逐步接收数据"""
    r = generate_data()
    return StreamingResponse(r, media_type="text/event-stream")
    model = claude_chat_request.model
    if model not in [model.value for model in ClaudeModels]:
        return JSONResponse(
            status_code=400,
            content={"error": f"Model not found."},
        )
    conversation_id = "test"
    conversation_id = claude_chat_request.conversation_id
    try:
        if not conversation_id:
            conversation = claude_client.create_new_chat()
            conversation_id = conversation["uuid"]
            logger.info(f"Created new conversation with id: {conversation_id}")
    except Exception as e:
        logger.error(f"Meet an error: {e}")
        return ("error: ", e)

    message = claude_chat_request.message
    is_stream = claude_chat_request.stream

    if is_stream:
        return StreamingResponse(
            claude_client.stream_message(message, conversation_id, model),
            media_type="text/event-stream",

            # headers={"conversation_id": conversation_id}  # 这里通过header返回conversation_id

        )
    else:
        res = claude_client.send_message(message, conversation_id, model)
        return res

