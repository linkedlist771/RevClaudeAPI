import asyncio
import json
from typing import List

import requests
from httpx import AsyncClient

from front_configs import *


def build_client_headers() -> dict:
    headers = {
        "APIAUTH": CLAUDE_BACKEND_API_APIAUTH,
        "Content-Type": "application/json",
        "Cookie": "adminKey=ThisIsAPassword",
    }
    return headers


def delete_sessions(ids: List[int]):
    url = f"{CLAUDE_BACKEND_API_USER_URL}/delete"
    payload = json.dumps({"ids": ids})
    headers = build_client_headers()
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code != 200:
        raise Exception(
            f"Failed to delete sessions. Status code: {response.status_code}"
        )


async def get_api_key_information(api_key: str):
    async with AsyncClient() as client:
        headers = build_client_headers()
        url = f"{CLAUDE_BACKEND_API_USER_URL}/page/"
        payload = {"page": 1, "size": 20, "keyWord": api_key}
        res = await client.post(url, headers=headers, json=payload, timeout=60)
        res_json = res.json()
        data = res_json.get("data")
        data = data["list"]
        result = next((i for i in data if i.get("userToken") == api_key), None)
        return result


async def get_all_api_key_information(user_tokens: List[str]):
    tasks = [get_api_key_information(token) for token in user_tokens]
    return await asyncio.gather(*tasks)


def delete_batch_api_keys(api_keys: List[str], batch_size: int = 50):
    # Get all user data asynchronously
    user_infos = asyncio.run(get_all_api_key_information(api_keys))
    # Extract IDs from user info
    ids_to_delete = [
        user_info.get("id")
        for user_info in user_infos
        if user_info and user_info.get("id")
    ]
    # Delete in batches
    for i in range(0, len(ids_to_delete), batch_size):
        batch = ids_to_delete[i : i + batch_size]
        delete_sessions(batch)
    message = f"Deleted a total of {len(ids_to_delete)} sessions"
    return message
