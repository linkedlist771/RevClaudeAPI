from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import Header, HTTPException
from api_key_manage import APIKeyManager, get_api_key_manager


from schemas import ClaudeChatRequest
from loguru import logger

from models import ClaudeModels

# This in only for claude router, I do not use the


# async def validate_api_key(
#     api_key: str = Header(None), manager: APIKeyManager = Depends(get_api_key_manager)
# ):
async def validate_api_key(request: Request, manager: APIKeyManager = Depends(get_api_key_manager)
):
    # Authorization
    logger.info(f"headers: {request.headers}")
    api_key = request.headers.get("Authorization")
    logger.info(f"checking api key: {api_key}")
    if api_key is None or not manager.is_api_key_valid(api_key):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


router = APIRouter(dependencies=[Depends(validate_api_key)])


def obtain_claude_client():
    from main import CLAUDE_CLIENT

    return CLAUDE_CLIENT


async def patched_generate_data(original_generator, conversation_id):
    # 首先发送 conversation_id
    yield f"<{conversation_id}>"

    # 然后，对原始生成器进行迭代，产生剩余的数据
    async for data in original_generator:
        yield data


@router.get("/list_conversations")
async def list_conversations(claude_client=Depends(obtain_claude_client)):
    return claude_client.list_all_conversations()
    # return {"message": "Hello World"}


@router.get("/list_models")
async def list_models():
    return [model.value for model in ClaudeModels]


@router.post("/chat")
async def chat(
    claude_chat_request: ClaudeChatRequest, claude_client=Depends(obtain_claude_client)
):
    model = claude_chat_request.model
    if model not in [model.value for model in ClaudeModels]:
        return JSONResponse(
            status_code=400,
            content={"error": f"Model not found."},
        )
    conversation_id = claude_chat_request.conversation_id
    # conversation_id = "test"

    try:
        if not conversation_id:
            conversation = claude_client.create_new_chat(model=model)
            logger.info(f"Created new conversation: {conversation}")
            logger.info(f"Created new conversation: {conversation}")
            conversation_id = conversation["uuid"]
            logger.info(f"Created new conversation with id: {conversation_id}")
    except Exception as e:
        logger.error(f"Meet an error: {e}")
        return ("error: ", e)

    message = claude_chat_request.message
    is_stream = claude_chat_request.stream

    if is_stream:
        streaming_res = claude_client.stream_message(message, conversation_id, model)
        streaming_res = patched_generate_data(streaming_res, conversation_id)
        return StreamingResponse(
            streaming_res,
            media_type="text/event-stream",
            headers={
                "conversation_id": conversation_id
            },  # 这里通过header返回conversation_id
        )
    else:
        res = claude_client.send_message(message, conversation_id, model)
        return res
