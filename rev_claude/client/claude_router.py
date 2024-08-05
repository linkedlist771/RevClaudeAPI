import asyncio
from functools import partial
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import HTTPException, File, UploadFile, Form

from rev_claude.api_key.api_key_manage import APIKeyManager, get_api_key_manager

from rev_claude.client.claude import upload_attachment_for_fastapi
from rev_claude.client.client_manager import ClientManager
from rev_claude.configs import (
    NEW_CONVERSATION_RETRY,
    USE_MERMAID_AND_SVG,
    CLAUDE_OFFICIAL_USAGE_INCREASE,
)
from rev_claude.history.conversation_history_manager import (
    conversation_history_manager,
    ConversationHistoryRequestInput,
    Message,
    RoleType,
)
from rev_claude.prompts_builder.artifacts_render_prompt import ArtifactsRendererPrompt
from rev_claude.prompts_builder.svg_renderer_prompt import SvgRendererPrompt
from rev_claude.schemas import (
    ClaudeChatRequest,
    ObtainReverseOfficialLoginRouterRequest,
)
from loguru import logger

from rev_claude.models import ClaudeModels
from rev_claude.status_code.status_code_enum import HTTP_480_API_KEY_INVALID
from rev_claude.utils.sse_utils import build_sse_data


# This in only for claude router, I do not use the


# async def validate_api_key(
#     api_key: str = Header(None), manager: APIKeyManager = Depends(get_api_key_manager)
# ):
async def validate_api_key(
    request: Request, manager: APIKeyManager = Depends(get_api_key_manager)
):

    api_key = request.headers.get("Authorization")
    # logger.info(f"checking api key: {api_key}")
    if api_key is None or not manager.is_api_key_valid(api_key):
        raise HTTPException(
            status_code=HTTP_480_API_KEY_INVALID,
            detail="APIKEY已经过期或者不存在，请检查您的APIKEY是否正确。",
        )
    manager.increment_usage(api_key)
    logger.info(f"API key:\n{api_key}")
    logger.info(manager.get_apikey_information(api_key))
    # 尝试激活 API key
    active_message = manager.activate_api_key(api_key)
    logger.info(active_message)


router = APIRouter(dependencies=[Depends(validate_api_key)])


def obtain_claude_client():

    basic_clients, plus_clients = ClientManager().get_clients()

    return {
        "basic_clients": basic_clients,
        "plus_clients": plus_clients,
    }


async def patched_generate_data(original_generator, conversation_id, hrefs=None):
    # 首先发送 conversation_id
    # 然后，对原始生成器进行迭代，产生剩余的数据
    async for data in original_generator:
        yield build_sse_data(message=data, id=conversation_id)
    if hrefs:
        for href in hrefs:
            yield build_sse_data(message=href, id=conversation_id)

    yield build_sse_data(message="closed", id=conversation_id)


@router.get("/list_models")
async def list_models():
    return [model.value for model in ClaudeModels]


@router.post("/convert_document")
async def convert_document(
    file: UploadFile = File(...),
):
    logger.info(f"Uploading file: {file.filename}")
    response = await upload_attachment_for_fastapi(file)
    return response


@router.post("/upload_image")
async def upload_image(
    file: UploadFile = File(...),
    client_idx: int = Form(...),
    client_type: str = Form(...),
    clients=Depends(obtain_claude_client),
):
    logger.info(f"Uploading file: {file.filename}")
    basic_clients = clients["basic_clients"]
    plus_clients = clients["plus_clients"]
    if client_type == "plus":
        claude_client = plus_clients[client_idx]
    else:
        claude_client = basic_clients[client_idx]
    response = await claude_client.upload_images(file)
    return response


async def push_assistant_message_callback(
    request: ConversationHistoryRequestInput,
    messages: list[Message],
    hrefs: list[str] = None,
    assistant_message: str = "",
):
    messages.append(
        Message(
            content=assistant_message,
            role=RoleType.ASSISTANT,
        )
    )
    if hrefs:
        hrefs_str = "".join(hrefs)
        messages[-1].content += hrefs_str

    conversation_history_manager.push_message(request, messages)


@router.post("/obtain_reverse_official_login_router")
async def obtain_reverse_official_login_router(
    request: Request,
    login_router_request: ObtainReverseOfficialLoginRouterRequest,
    clients=Depends(obtain_claude_client),
    manager: APIKeyManager = Depends(get_api_key_manager),
):
    api_key = request.headers.get("Authorization")
    has_reached_limit = manager.has_exceeded_limit(api_key)
    if has_reached_limit:
        # 首先check一下用户是不是被删除了
        is_deleted = not manager.is_api_key_valid(api_key)
        if is_deleted:

            return JSONResponse(
                content={
                    "message": "由于滥用API key，已经被删除，如有疑问，请联系管理员。",
                    "valid": False,
                },
            )
        message = manager.generate_exceed_message(api_key)
        logger.info(f"API {api_key} has reached the limit.")
        return JSONResponse(
            content={"message": message, "valid": False},
        )
        # 这里都check完成了
    # 只要传入的api_key是唯一标识符后面的也是唯一唯一标识符
    # 用他的api_key作为唯一标识符。
    client_idx = login_router_request.client_idx
    __client_type = login_router_request.client_type
    __client_type = __client_type.replace("normal", "basic")
    client_type = __client_type + "_clients"
    client = clients[client_type][client_idx]
    # 这里还要加上使用次数， 差点忘了。
    manager.increment_usage(api_key, CLAUDE_OFFICIAL_USAGE_INCREASE)
    res = await client.retrieve_reverse_official_route(unique_name=api_key)
    return JSONResponse(
        content={"data": res, "valid": True},
    )


@router.post("/chat")
async def chat(
    request: Request,
    claude_chat_request: ClaudeChatRequest,
    clients=Depends(obtain_claude_client),
    manager: APIKeyManager = Depends(get_api_key_manager),
):
    api_key = request.headers.get("Authorization")
    has_reached_limit = manager.has_exceeded_limit(api_key)
    if has_reached_limit:
        # 首先check一下用户是不是被删除了
        is_deleted = not manager.is_api_key_valid(api_key)
        if is_deleted:
            return StreamingResponse(
                build_sse_data(
                    message="由于滥用API key，已经被删除，如有疑问，请联系管理员。"
                ),
                media_type="text/event-stream",
            )
        message = manager.generate_exceed_message(api_key)
        # return JSONResponse(status_code=403, content=message)
        logger.info(f"API {api_key} has reached the limit.")
        return StreamingResponse(
            build_sse_data(message=message), media_type="text/event-stream"
        )
    logger.info(f"Input chat request request: \n{claude_chat_request.model_dump()}")
    basic_clients = clients["basic_clients"]
    plus_clients = clients["plus_clients"]
    client_idx = claude_chat_request.client_idx
    model = claude_chat_request.model
    # if model not in [model.value for model in ClaudeModels]:
    #     # return JSONResponse(
    #     #     status_code=400,
    #     #     content={"message": f"Model: not found.\n" f"未找到模型:"},
    #     # )
    #     return StreamingResponse(
    #         build_sse_data(message="Model: not found.\n" f"未找到模型:"),
    #         media_type="text/event-stream",
    #     )
    conversation_id = claude_chat_request.conversation_id

    client_type = claude_chat_request.client_type
    client_type = "plus" if client_type == "plus" else "basic"
    if (not manager.is_plus_user(api_key)) and (client_type == "plus"):
        # return JSONResponse(
        #     status_code=403,
        #     content={
        #         "message": f"您的 API key 不是 Plus 用户，请升级您的套餐以访问此账户。"
        #     },
        # )
        return StreamingResponse(
            build_sse_data(
                message="您的登录秘钥不是Plus 用户，请升级您的套餐以访问此账户。"
            ),
            media_type="text/event-stream",
        )

    if (client_type == "basic") and ClaudeModels.model_is_plus(model):
        # return JSONResponse(
        #     status_code=403,
        #     content={
        #         "message": f"客户端是基础用户，但模型是 Plus 模型，请切换到 Plus 客户端。"
        #     },
        # )
        return StreamingResponse(
            build_sse_data(
                message="客户端是基础用户，但模型是 Plus 模型，请切换到 Plus 客户端。"
            ),
            media_type="text/event-stream",
        )
    # logger.info(f"client_idx: {client_idx}, client_idx type: {type(client_idx)}")

    if client_type == "plus":
        claude_client = plus_clients[client_idx]
    else:
        claude_client = basic_clients[client_idx]
    raw_message = claude_chat_request.message
    if not conversation_id:
        conversation_id = str(uuid4())

    message = claude_chat_request.message
    is_stream = claude_chat_request.stream

    conversation_history_request = ConversationHistoryRequestInput(
        conversation_type=client_type,
        api_key=api_key,
        client_idx=client_idx,
        conversation_id=conversation_id,
        model=model,
    )
    messages: list[Message] = []
    messages.append(
        Message(
            content=raw_message,
            role=RoleType.USER,
        )
    )

    # 处理文件的部分
    attachments = claude_chat_request.attachments
    if attachments is None:
        attachments = []

    # conversation_history_manager

    files = claude_chat_request.files
    if files is None:
        files = []

    # 处理message的部分， 如果需要搜索的话:
    logger.debug(f"Need web search: {claude_chat_request.need_web_search}")
    hrefs = []
    if claude_chat_request.need_web_search:
        from rev_claude.prompts_builder.duckduck_search_prompt import (
            DuckDuckSearchPrompt,
        )

        # here we choose a number from 3 to 5
        message, hrefs = await DuckDuckSearchPrompt(
            prompt=message,
        ).render_prompt()
        logger.info(f"Prompt After search: \n{message}")
    call_back = partial(
        push_assistant_message_callback, conversation_history_request, messages, hrefs
    )
    if is_stream:
        streaming_res = claude_client.stream_message(
            message,
            conversation_id,
            model,
            client_type=client_type,
            client_idx=client_idx,
            attachments=attachments,
            files=files,
            call_back=call_back,
            api_key=api_key,
        )
        streaming_res = patched_generate_data(streaming_res, conversation_id, hrefs)
        return StreamingResponse(
            streaming_res,
            media_type="text/event-stream",
            # headers={
            #     "conversation_id": conversation_id
            # },  # 这里通过header返回conversation_id
        )
    else:

        res = claude_client.send_message(message, conversation_id, model)
        return res
