import asyncio
from tqdm.asyncio import tqdm
from loguru import logger
from rev_claude.client.claude import Client
import traceback


REGISTER_MAY_RETRY = 1
REGISTER_MAY_RETRY_RELOAD = 15  # in reload there are more retries

REGISTER_WAIT = 3


async def _register_clients(
    cookie: str, cookie_key: str, cookie_type: str, reload: bool = False
):
    retry_count = REGISTER_MAY_RETRY if not reload else REGISTER_MAY_RETRY_RELOAD
    from rev_claude.cookie.claude_cookie_manage import get_cookie_manager

    cookie_manager = get_cookie_manager()
    while retry_count > 0:
        try:
            client = Client(cookie, cookie_key)
            if not reload:
                # first , try to obtain it from the reids, if not then register it
                organization_id = await cookie_manager.get_organization_id(cookie_key)
                if organization_id:
                    client.organization_id = organization_id
                else:
                    logger.debug(f"organization_id got from redis: {organization_id}")

                    organization_id = await client.__set_organization_id__()
                    await cookie_manager.update_organization_id(
                        cookie_key, organization_id
                    )
                    logger.info(f"Registered the {cookie_type} client: {client}")
            else:
                organization_id = await client.__set_organization_id__()
                await cookie_manager.update_organization_id(cookie_key, organization_id)
                logger.info(f"Reloaded the {cookie_type} client: {client}")

            return client
        # res = response.json()
        # logger.debug(f"res : {res}")
        # if "Invalid" in res:
        #     raise ValueError("Invalid cookie")
        # uuid = res[0]["uuid"]

        except Exception as e:
            if "We are unable to serve your request" in str(e):
                retry_count -= 1
            else:
                retry_count = 0
            logger.error(f"error:" f"{str (e)}")
            logger.error(
                f"Failed to register the {cookie_type} client, retrying... {retry_count} retries left. \n Error: {traceback.format_exc()}"
            )
            if retry_count == 0:
                logger.error(
                    f"Failed to register the {cookie_type} client after several retries."
                )
                # after all the retries, we still failed, we should delete the organization_id and if relad
                if reload:
                    await cookie_manager.delete_organization_id(cookie_key)

                return None
            await asyncio.sleep(REGISTER_WAIT)  # 在重试前暂停1秒


async def register_clients(
    _basic_cookies,
    _basic_cookie_keys,
    _plus_cookies,
    _plus_cookie_keys,
    reload: bool = False,
):
    basic_tasks = []
    plus_tasks = []
    _basic_clients = []
    _plus_clients = []
    for plus_cookie, plus_cookie_key in zip(_plus_cookies, _plus_cookie_keys):
        task = asyncio.create_task(
            _register_clients(plus_cookie, plus_cookie_key, "plus", reload)
        )
        plus_tasks.append(task)

    for basic_cookie, basic_cookie_key in zip(_basic_cookies, _basic_cookie_keys):
        task = asyncio.create_task(
            _register_clients(basic_cookie, basic_cookie_key, "basic", reload)
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
