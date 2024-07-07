from rev_claude.client.claude import Client
from loguru import logger
import asyncio


async def main():
     client = Client(cookie="")
     await client.__set_organization_id__()
     # test the proxy one by one
     try:
         # idx, client = next(self.plus_clients_cycle).items()
         conversation = await client.create_new_chat(model="claude-3-5-sonnet-20240620")
         logger.debug(
             f"Created new conversation with response: \n{conversation}"
         )
         conversation_id = conversation["uuid"]
         #
         # pay_load["conversation_id"] = conversation_id
         # pay_load["client_type"] = "plus"
         # pay_load["client_idx"] = idx
         # async for _ in client.stream_message(**pay_load, timeout=120):
         #     pass
         # logger.debug(f"res: {res}")]
     except Exception as e:

         logger.error(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
