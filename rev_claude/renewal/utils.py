from datetime import datetime, timedelta
import pytz
from httpx import AsyncClient
from pydantic import BaseModel
from typing import Optional

from rev_claude.configs import CLAUDE_BACKEND_API_APIAUTH, CLAUDE_BACKEND_API_USER_URL
from rev_claude.utils.time_zone_utils import get_shanghai_time


class APIKeyInfo(BaseModel):
    userToken: str
    expireTime: str
    isPlus: int = 1
    remark: Optional[str] = None
    createTime: Optional[str] = None
    deleted_at: Optional[str] = None
    id: Optional[int] = None
    isUsed: int = 1
    updateTime: Optional[str] = None


def build_client_headers() -> dict:
    headers = {
        "APIAUTH": CLAUDE_BACKEND_API_APIAUTH,
        "Content-Type": "application/json"
    }
    return headers


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


async def update_api_key_information(api_key_info: dict):
    async with AsyncClient() as client:
        headers = build_client_headers()
        url = f"{CLAUDE_BACKEND_API_USER_URL}/update"
        res = await client.post(url, headers=headers, json=api_key_info, timeout=60)
        return res.json()


async def create_api_key(api_key: str, expire_time: str):
    async with AsyncClient() as client:
        headers = build_client_headers()
        url = f"{CLAUDE_BACKEND_API_USER_URL}/add"
        api_key_info = APIKeyInfo(
            userToken=api_key,
            expireTime=expire_time,
            createTime=get_shanghai_time().strftime("%Y-%m-%d %H:%M:%S")
        )
        res = await client.post(url, headers=headers, json=api_key_info.dict(), timeout=60)
        return res.json()


async def renew_api_key(api_key: str, days: float = 30):
    """
    Renew an API key for the specified number of days.

    Args:
        api_key (str): The API key to renew
        days (float): Number of days to extend the API key validity

    Returns:
        dict: Updated API key information
    """
    # Get current API key information
    api_key_info = await get_api_key_information(api_key)

    current_time = get_shanghai_time()
    shanghai_tz = pytz.timezone("Asia/Shanghai")
    extension_period = timedelta(days=days)
    #  "isUsed": 1,

    if api_key_info:
        # API key exists - handle renewal
        expire_time = shanghai_tz.localize(datetime.strptime(api_key_info["expireTime"], "%Y-%m-%d %H:%M:%S"))

        # 首先判断有没有被使用？ 如果没有被使用的话， 那么就在原始的基础上加上 然后返回
        # extension_period
        is_used = api_key_info.get("isUsed", 0)
        if not is_used:
            new_expire_time = expire_time + extension_period
        # 被使用并且过期了
        else:
            # If expired, start from current time
            if expire_time < current_time:
                new_expire_time = current_time + extension_period
            else:
                # If not expired, add extension to current expiry
                new_expire_time = expire_time + extension_period

        # Update API key information
        api_key_info["expireTime"] = new_expire_time.strftime("%Y-%m-%d %H:%M:%S")
        api_key_info["updateTime"] = current_time.strftime("%Y-%m-%d %H:%M:%S")

        # Submit update
        result = await update_api_key_information(api_key_info)

    else:
        # API key doesn't exist - create new one
        new_expire_time = current_time + extension_period
        result = await create_api_key(
            api_key,
            new_expire_time.strftime("%Y-%m-%d %H:%M:%S")
        )

    return result
