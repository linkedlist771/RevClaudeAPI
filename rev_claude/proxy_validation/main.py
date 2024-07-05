from loguru import logger
import httpx
import asyncio

from rev_claude.client.client_manager import ClientManager
from rev_claude.proxy_validation.proxies import PROXIES



async def get_clients():
    await ClientManager().load_clients(reload=False)



class ProxyValidator():

    def __init__(self):
        self.basic_clients, self.plus_clients = ClientManager().get_clients()

    async def validate_proxy(self):
        pay_load ={
            "stream": True,
            "prompt": "画一只小猪",
            "model": "claude-3-5-sonnet-20240620",

            "attachments": None,
            "files": None,
            "need_web_search": False
        }
        for idx, proxy in enumerate(PROXIES):
            # test the proxy one by one
            logger.debug(f"Testing proxy, idx: {idx}, proxy: {proxy}")
            res = await self.plus_clients[0].stream_message(**pay_load, timeout=120)
            # logger.debug(f"res: {res}")

async def main():
    await get_clients()
    validator = ProxyValidator()
    await validator.validate_proxy()

if __name__ == "__main__":
    asyncio.run(main())