import asyncio
from itertools import cycle

import httpx
from loguru import logger

from rev_claude.client.client_manager import ClientManager
from rev_claude.proxy_validation.proxies import PROXIES


async def get_clients():
    await ClientManager().load_clients(reload=False)


class ProxyValidator:
    def __init__(self):
        self.basic_clients, self.plus_clients = ClientManager().get_clients()
        # this is a dict\
        self.plus_clients_idx_cycle = cycle(list(self.plus_clients.keys()))

    async def validate_proxy(self):
        pay_load = {
            "prompt": "画一只小猪",
            "model": "claude-3-5-sonnet-20240620",
            "attachments": None,
            "files": None,
        }
        valid_proxies = []
        for idx, proxy in enumerate(PROXIES):
            # test the proxy one by one
            try:
                logger.debug(f"Testing proxy, idx: {idx}, proxy: {proxy}")
                # idx, client = next(self.plus_clients_cycle).items()
                idx = next(self.plus_clients_idx_cycle)
                client = self.plus_clients[idx]
                conversation = await client.create_new_chat(
                    model="claude-3-5-sonnet-20240620"
                )
                logger.debug(
                    f"Created new conversation with response: \n{conversation}"
                )
                conversation_id = conversation["uuid"]
                # pay_load["conversation_id"] = conversation_id
                # pay_load["client_type"] = "plus"
                # pay_load["client_idx"] = idx
                # async for _ in client.stream_message(**pay_load, timeout=120):
                #     pass
                # logger.debug(f"res: {res}")]
                valid_proxies.append(proxy)
            except Exception as e:
                logger.error(f"Error: {e}")
                continue
        logger.debug(f"Valid proxies: {valid_proxies}")


async def main():
    await get_clients()
    validator = ProxyValidator()
    await validator.validate_proxy()


if __name__ == "__main__":
    asyncio.run(main())
