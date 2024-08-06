import asyncio

from starlette.responses import StreamingResponse
from tqdm.asyncio import tqdm

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

    # async def stream_message(
    #     self,
    #     prompt,
    #     conversation_id,
    #     model,
    #     client_type,
    #     client_idx,
    #     attachments=None,
    #     files=None,
    #     call_back=None,
    #     timeout=120,
    # ):


async def simple_new_chat(claude_client, client_type, client_idx):
    model = ClaudeModels.SONNET_3_5.value
    conversation_id = await try_to_create_new_conversation(claude_client, model)
    try:
        async for data in claude_client.stream_message(
            prompt="Say, yes",
            conversation_id=conversation_id,
            model=model,
            client_type=client_type,
            client_idx=client_idx,
            attachments=[],
        ):
            logger.info(data)
    except Exception as e:
        from traceback import format_exc

        logger.error(f"Error: {e}")
        # logger.error(f"Error: {e}")


async def check_reverse_official_usage_limits():
    from rev_claude.client.client_manager import ClientManager

    basic_clients, plus_clients = ClientManager().get_clients()
    status_list = get_client_status(basic_clients, plus_clients)
    clients = [
        {
            "client": (
                plus_clients[status.idx]
                if status.type == "plus"
                else basic_clients[status.idx]
            ),
            "type": status.type,
            "idx": status.idx,
        }
        for status in status_list
        if status.is_session_login
    ]
    logger.info(f"Found {len(clients)} active clients to check")

    async def check_client(client):
        try:
            logger.debug(f"Testing client {client['type']} {client['idx']}")
            await simple_new_chat(client["client"], client["type"], client["idx"])
            logger.debug(f"Completed test for client {client['type']} {client['idx']}")
        except Exception as e:
            logger.error(f"Error testing client {client['type']} {client['idx']}: {e}")

    try:
        tasks = [check_client(client) for client in clients]
        await tqdm.gather(*tasks, desc="Checking clients", unit="client")
    except Exception as e:
        logger.error(f"Error during client checks: {e}")

    logger.info("Completed check_reverse_official_usage_limits")
