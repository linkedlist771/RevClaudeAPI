import asyncio
from tqdm.asyncio import tqdm
from loguru import logger
from rev_claude.client.claude import Client


async def register_basic_client(basic_cookie, basic_cookie_key):
    try:
        basic_client = await Client.__async__init__(basic_cookie, basic_cookie_key)
        logger.info(f"Register the basic client: {basic_client}")
        return basic_client
    except Exception as e:
        logger.error(f"Failed to register the basic client: {e}")
        return None


async def register_plus_client(plus_cookie, plus_cookie_key):
    try:
        plus_client = await Client.__async__init__(plus_cookie, plus_cookie_key)
        logger.info(f"Register the plus client: {plus_client}")
        return plus_client
    except Exception as e:
        logger.error(f"Failed to register the plus client: {e}")
        return None


async def register_clients(_basic_cookies, _basic_cookie_keys, _plus_cookies, _plus_cookie_keys):
    basic_tasks = []
    plus_tasks = []
    _basic_clients = []
    _plus_clients = []

    async for basic_cookie, basic_cookie_key in tqdm(
            zip(_basic_cookies, _basic_cookie_keys), desc="Registering basic clients"
    ):
        task = asyncio.create_task(register_basic_client(basic_cookie, basic_cookie_key))
        basic_tasks.append(task)

    async for plus_cookie, plus_cookie_key in tqdm(
            zip(_plus_cookies, _plus_cookie_keys), desc="Registering plus clients"
    ):
        task = asyncio.create_task(register_plus_client(plus_cookie, plus_cookie_key))
        plus_tasks.append(task)

    basic_clients = await asyncio.gather(*basic_tasks)
    plus_clients = await asyncio.gather(*plus_tasks)

    _basic_clients.extend(filter(None, basic_clients))
    _plus_clients.extend(filter(None, plus_clients))
    return _basic_clients, _plus_clients


