import asyncio
from tqdm.asyncio import tqdm
from loguru import logger
from rev_claude.client.claude import Client


async def register_basic_client(basic_cookie, basic_cookie_key):
    try:
        basic_client = Client(basic_cookie, basic_cookie_key)
        await basic_client.__set_organization_id__()
        logger.info(f"Register the basic client: {basic_client}")
        return basic_client
    except Exception as e:
        logger.error(f"Failed to register the basic client: {e}")
        return None


async def register_plus_client(plus_cookie, plus_cookie_key):
    try:
        plus_client = Client(plus_cookie, plus_cookie_key)
        await plus_client.__set_organization_id__()
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

    for basic_cookie, basic_cookie_key in  zip(_basic_cookies, _basic_cookie_keys):
        task = asyncio.create_task(register_basic_client(basic_cookie, basic_cookie_key))
        basic_tasks.append(task)

    for plus_cookie, plus_cookie_key in zip(_plus_cookies, _plus_cookie_keys):
        plus_client = await register_plus_client(plus_cookie, plus_cookie_key)
        _plus_clients.append(plus_client)

    basic_clients = await asyncio.gather(*basic_tasks)

    _basic_clients.extend(filter(None, basic_clients))
    _plus_clients = filter(None, _plus_clients)
    logger.debug(f"registered basic clients: {len(_basic_clients)}")
    logger.debug(f"registered plus clients: {len(_plus_clients)}")
    return _basic_clients, _plus_clients


