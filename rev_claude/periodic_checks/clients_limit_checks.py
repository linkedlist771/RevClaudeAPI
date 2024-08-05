import asyncio

from starlette.responses import StreamingResponse

from rev_claude.configs import NEW_CONVERSATION_RETRY
from rev_claude.models import ClaudeModels
from rev_claude.utils.sse_utils import build_sse_data
from utility import get_client_status
from loguru import logger

async def try_to_create_new_conversation(claude_client, model):
    max_retry = NEW_CONVERSATION_RETRY
    current_retry = 0
    while current_retry < max_retry:
        try:
                try:
                    conversation = await claude_client.create_new_chat(model=model)
                    logger.debug(
                        f"Created new conversation with response: \n{conversation}"
                    )
                    conversation_id = conversation["uuid"]
                    # now we can reredenert the user's prompt

                    await asyncio.sleep(2)  # 等待两秒秒,创建成功后
                    return conversation_id
                except Exception as e:
                    current_retry += 1
                    logger.error(
                        f"Failed to create conversation. Retry {current_retry}/{max_retry}. Error: {e}"
                    )
                    if current_retry == max_retry:
                        logger.error(
                            f"Failed to create conversation after {max_retry} retries."
                        )
                        return
                        # return ("error: ", e)
                    else:
                        logger.info("Retrying in 2 second...")
                        await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Meet an error: {e}")
            return


async def simple_new_chat(claude_client):
    model = ClaudeModels.SONNET_3_5
    conversation_id = await try_to_create_new_conversation(claude_client, model)

async def check_reverse_official_usage_limits():
    from rev_claude.client.client_manager import ClientManager

    basic_clients, plus_clients = ClientManager().get_clients()
    status_list = get_client_status(basic_clients, plus_clients)
    clients = []
    for status in status_list:
        if status.is_session_login:
            client_type = status.type
            client_idx = status.idx
            if client_type == "plus":
                clients.append(plus_clients[client_idx])
            else:
                clients.append(basic_clients[client_idx])
    # 完成了， 然后就是检测状态





