import asyncio
from tqdm.asyncio import tqdm
from loguru import logger
from rev_claude.client.claude import Client
import traceback

REGISTER_MAY_RETRY = 3
REGISTER_WAIT = 3


async def register_basic_client(basic_cookie, basic_cookie_key):
    retry_count = REGISTER_MAY_RETRY  # 设置最大重试次数
    while retry_count > 0:
        try:
            basic_client = Client(basic_cookie, basic_cookie_key)
            await basic_client.__set_organization_id__()
            logger.info(f"Registered the basic client: {basic_client}")
            return basic_client
        except Exception as e:
            retry_count -= 1
            logger.error(
                f"Failed to register the basic client, retrying... {retry_count} retries left. \n Error: {traceback.format_exc()}"
            )
            if retry_count == 0:
                logger.error(
                    "Failed to register the basic client after several retries."
                )
                return None
            await asyncio.sleep(REGISTER_WAIT)  # 在重试前暂停1秒


async def register_plus_client(plus_cookie, plus_cookie_key):
    retry_count = REGISTER_MAY_RETRY  # 设置最大重试次数
    while retry_count > 0:
        try:
            plus_client = Client(plus_cookie, plus_cookie_key)
            await plus_client.__set_organization_id__()
            logger.info(f"Registered the plus client: {plus_client}")
            return plus_client
        except Exception as e:
            retry_count -= 1
            logger.error(
                f"Failed to register the plus client, retrying... {retry_count} retries left. \n Error: {traceback.format_exc()}"
            )
            if retry_count == 0:
                logger.error(
                    "Failed to register the plus client after several retries."
                )
                return None
            await asyncio.sleep(REGISTER_WAIT)  # 在重试前暂停1秒


async def register_clients(
    _basic_cookies, _basic_cookie_keys, _plus_cookies, _plus_cookie_keys
):
    basic_tasks = []
    plus_tasks = []
    _basic_clients = []
    _plus_clients = []
    for plus_cookie, plus_cookie_key in zip(_plus_cookies, _plus_cookie_keys):
        task = asyncio.create_task(
            register_plus_client(plus_cookie, plus_cookie_key)
        )
        plus_tasks.append(task)

    for basic_cookie, basic_cookie_key in zip(_basic_cookies, _basic_cookie_keys):
        task = asyncio.create_task(
            register_basic_client(basic_cookie, basic_cookie_key)
        )
        basic_tasks.append(task)

    plus_clients = await asyncio.gather(*plus_tasks)
    basic_clients = await asyncio.gather(*basic_tasks)




    _basic_clients.extend(filter(None, basic_clients))
    _plus_clients.extend(filter(None, plus_clients))
    logger.debug(
        f"registered basic clients: {len(_basic_clients)} / {len(_basic_cookies)}"
    )
    logger.debug(
        f"registered plus clients: {len(_plus_clients)} / {len(_plus_cookies)}"
    )
    return _basic_clients, _plus_clients
