import httpx
from typing import Union
from front_configs import CLAUDE_AUDIT_BASE_URL

async def get_single_conversation(api_key: str, conversation_id: Union[str, None] = None):
    async with httpx.AsyncClient() as client:
        url = f"{CLAUDE_AUDIT_BASE_URL}/conversations/{api_key}"
        if conversation_id:
            url = f"{url}?conversation_id={conversation_id}"
        response = await client.post(url, timeout=600)
        return response.json()


async def get_all_conversations(time_filter: str):
    async with httpx.AsyncClient() as client:
        url = f"{CLAUDE_AUDIT_BASE_URL}/conversations_all?time_filter={time_filter}"
        # params = {"time_filter": time_filter}
        response = await client.post(url, timeout=600)
        return response.json()



