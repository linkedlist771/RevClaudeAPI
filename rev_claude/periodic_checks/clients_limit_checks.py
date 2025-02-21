import asyncio
import time

from loguru import logger
from tqdm.asyncio import tqdm

from rev_claude.configs import (CLAUDE_CLIENT_LIMIT_CHECKS_PROMPT,
                                NEW_CONVERSATION_RETRY)
from rev_claude.models import ClaudeModels
from rev_claude.utility import get_client_status


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
                else:
                    logger.info("Retrying in 2 second...")
                    await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Meet an error: {e}")
            return


async def simple_new_chat(claude_client, client_type, client_idx):
    model = ClaudeModels.SONNET_3_5.value
    conversation_id = await try_to_create_new_conversation(claude_client, model)
    messages = ""
    try:
        async for data in claude_client.stream_message(
            prompt=CLAUDE_CLIENT_LIMIT_CHECKS_PROMPT,
            conversation_id=conversation_id,
            model=model,
            client_type=client_type,
            client_idx=client_idx,
            attachments=[],
        ):
            # logger.info(data)
            messages += data
    except Exception as e:
        from traceback import format_exc

        messages = f"Error: {e}\n{format_exc()}"
    return messages


async def __check_reverse_official_usage_limits():
    from rev_claude.client.client_manager import ClientManager

    start_time = time.perf_counter()
    basic_clients, plus_clients = ClientManager().get_clients()
    status_list = await get_client_status(basic_clients, plus_clients)
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
        # if status.is_session_login  就算不是官网登录的也要check。
    ]

    logger.info(f"Found {len(clients)} active clients to check")

    results = []

    # async def check_client(client):
    #     try:
    #         # logger.debug(f"Testing client {client['type']} {client['idx']}")
    #         res = await simple_new_chat(client["client"], client["type"], client["idx"])
    #         # logger.debug(
    #         #     f"Completed test for client {client['type']} {client['idx']}\n: {res}"
    #         # )
    #         return f"Client {client['type']} {client['idx']}: {res}"
    #     except Exception as e:
    #         error_msg = f"Error testing client {client['type']} {client['idx']}: {e}"
    #         logger.error(error_msg)
    #         return error_msg
    #
    #
    # try:
    #     # tasks = [asyncio.create_task(check_client(client)) for client in clients]
    #     #     # check_client(client) for client in clients]
    #     # results = await tqdm.gather(*tasks, desc="Checking clients", unit="client")
    #     results = []
    #     for client in clients:
    #         try:
    #             logger.debug(f"Testing client {client['type']} {client['idx']}")
    #             res = await simple_new_chat(client["client"], client["type"], client["idx"])
    #             logger.debug(f"Completed test for client {client['type']} {client['idx']}\n: {res}")
    #             results.append(f"Client {client['type']} {client['idx']}: {res}")
    #         except Exception as e:
    #             error_msg = f"Error testing client {client['type']} {client['idx']}: {e}"
    #             logger.error(error_msg)
    #             results.append(error_msg)
    #
    #         # 添加一个短暂的延迟，避免可能的限速问题
    #         await asyncio.sleep(1)
    #
    # except Exception as e:
    #     logger.error(f"Error during client checks: {e}")

    async def check_client(client):
        try:
            logger.debug(f"Testing client {client['type']} {client['idx']}")
            res = await simple_new_chat(client["client"], client["type"], client["idx"])
            logger.debug(
                f"Completed test for client {client['type']} {client['idx']}\n: {res}"
            )
            return f"Client {client['type']} {client['idx']}: {res}"
        except Exception as e:
            error_msg = f"Error testing client {client['type']} {client['idx']}: {e}"
            logger.error(error_msg)
            return error_msg

    async def process_batch(batch):
        return await asyncio.gather(*[check_client(client) for client in batch])

    results = []
    batch_size = 3  # 每批处理的客户端数量
    for i in range(0, len(clients), batch_size):
        batch = clients[i : i + batch_size]
        logger.info(
            f"Processing batch {i // batch_size + 1} of {len(clients) // batch_size + 1}"
        )
        batch_results = await process_batch(batch)
        results.extend(batch_results)
        if i + batch_size < len(clients):
            logger.info("Waiting between batches...")
            await asyncio.sleep(1)  # 批次之间的间隔

    logger.info("Completed check_reverse_official_usage_limits")

    # Print all results at the end
    logger.info("\nResults of client checks:")
    time_elapsed = time.perf_counter() - start_time
    logger.debug(f"Time elapsed: {time_elapsed:.2f} seconds")
    for result in results:
        logger.info(result)


async def check_reverse_official_usage_limits():
    # 使用 create_task，但不等待它完成
    task = asyncio.create_task(__check_reverse_official_usage_limits())
    return {"message": "Check started in background"}
