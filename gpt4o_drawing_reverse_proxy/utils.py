import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import requests
from configs import IMAGES_DIR, JS_DIR, ROOT, SERVER_BASE_URL, TARGET_URL
from loguru import logger
from tqdm.asyncio import tqdm

admin_username = "liuliu"
admin_password = "123.liu"


class SoruxGPTManager:
    def __init__(self, admin_username: str, admin_password: str):
        self.base_url = "https://gpt.soruxgpt.com/api"
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.token: Optional[str] = None
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://gpt.soruxgpt.com",
            "Referer": "https://gpt.soruxgpt.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
        }

    def generate_credentials(self, days: int, hours: int = 0) -> tuple:
        def generate_uuid_string() -> str:
            # Generate UUID and remove hyphens, take first 12 characters
            return str(uuid.uuid4()).replace("-", "")[:12]

        # Format: days_hours_randomstring
        prefix = f"{days}_{hours}_" if hours > 0 else f"{days}_"
        username = f"{prefix}{generate_uuid_string()}"
        password = generate_uuid_string()
        return username, password

    async def login(self) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/user/login",
                    headers=self.headers,
                    data={
                        "username": self.admin_username,
                        "password": self.admin_password,
                    },
                )
                response.raise_for_status()
                self.token = response.json()["Token"]
                return True
            except Exception as e:
                print(f"Login failed: {str(e)}")
                return False

    async def register_user(self, username: str, password: str) -> Optional[str]:
        if not self.token:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/agent/register",
                    headers=self.headers,
                    params={"token": self.token},
                    data={"username": username, "password": password},
                )
                response.raise_for_status()
                return response.json()["UserID"]
            except Exception as e:
                print(f"Registration failed for {username}: {str(e)}")
                return None

    async def add_node(self, user_id: str, expire_time: datetime) -> bool:
        if not self.token:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/agent/addNode",
                    headers=self.headers,
                    params={"token": self.token},
                    data={
                        "user_id": user_id,
                        "node_id": "185",
                        "time": expire_time.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                )
                response.raise_for_status()
                return True
            except Exception as e:
                print(f"Add node failed for user {user_id}: {str(e)}")
                return False

    async def get_user_info(
        self, user_name: str, current: int = 1, page_size: int = 8
    ) -> Optional[Dict]:
        """Get user information by username.

        Args:
            user_name: The username to search for
            current: Current page number (default: 1)
            page_size: Number of items per page (default: 8)

        Returns:
            Optional[Dict]: User information if successful, None if failed
        """
        if not self.token:
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/agent/getPartUsers",
                    headers=self.headers,
                    params={"token": self.token},
                    data={
                        "current": current,
                        "pageSize": page_size,
                        "UserName": user_name,
                    },
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Get user info failed for username {user_name}: {str(e)}")
                return e

    async def delete_user(self, user_name: str) -> Dict:
        """Delete a user account.

        Args:
            user_name: The username to delete

        Returns:
            Dict: Contains status and details of the deletion operation
        """
        if not self.token:
            return {"username": user_name, "success": False, "error": "No valid token"}

        try:
            user_info = await self.get_user_info(user_name)
            if (
                not user_info
                or not user_info.get("data")
                or len(user_info["data"]) == 0
            ):
                return {
                    "username": user_name,
                    "success": False,
                    "error": "User not found",
                }

            user_id = user_info["data"][0]["ID"]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/agent/delete",
                    headers=self.headers,
                    params={"token": self.token},
                    data={"user_id": user_id},
                )
                response.raise_for_status()
                return {"username": user_name, "success": True, "user_id": user_id}

        except Exception as e:
            return {"username": user_name, "success": False, "error": str(e)}

    async def batch_delete_users(self, user_names: List[str]) -> List[Dict]:
        """Batch delete multiple users.

        Args:
            user_names: List of usernames to delete

        Returns:
            List[Dict]: List of deletion results for each user
        """
        if not await self.login():
            return [
                {"username": username, "success": False, "error": "Failed to login"}
                for username in user_names
            ]

        if not self.token:
            return [
                {"username": username, "success": False, "error": "No valid token"}
                for username in user_names
            ]

        tasks = [self.delete_user(user_name) for user_name in user_names]
        results = await tqdm.gather(
            *tasks, desc="Deleting users", total=len(user_names)
        )
        return results

    async def set_user_limits(
        self,
        user_id: str,
        message_limited: int = 5,
        rate_refresh_time: int = 1,
        message_bucket_sum: int = 100,
        message_bucket_time: int = 180,
    ) -> bool:
        if not self.token:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/agent/limit",
                    headers=self.headers,
                    params={"token": self.token},
                    data={
                        "user_id": user_id,
                        "message_limited": str(message_limited),
                        "rate_refresh_time": str(rate_refresh_time),
                        "message_bucket_sum": str(message_bucket_sum),
                        "message_bucket_time": str(message_bucket_time),
                    },
                )
                response.raise_for_status()
                return True
            except Exception as e:
                print(f"Set limits failed for user {user_id}: {str(e)}")
                return False

    async def create_single_user(
        self,
        days: int,
        hours: int,
        i: int,
        message_limited: int = 5,
        rate_refresh_time: int = 1,
        message_bucket_sum: int = 100,
        message_bucket_time: int = 180,
    ) -> Dict:
        username, password = self.generate_credentials(days, hours)
        expire_time = datetime.now() + timedelta(days=days, hours=hours)

        user_id = await self.register_user(username, password)
        if not user_id:
            return {}

        node_added = await self.add_node(user_id, expire_time)
        limits_set = await self.set_user_limits(
            user_id,
            message_limited,
            rate_refresh_time,
            message_bucket_sum,
            message_bucket_time,
        )

        if node_added and limits_set:
            return {
                "formatted": f"{username}----{password}",
                "username": username,
                "password": password,
                "user_id": user_id,
                "expire_time": expire_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        return {}

    async def batch_create_users(
        self,
        count: int,
        days: int,
        hours: int = 0,
        batch_size: int = 5,
        message_limited: int = 5,
        rate_refresh_time: int = 1,
        message_bucket_sum: int = 100,
        message_bucket_time: int = 180,
    ) -> List[Dict]:
        if not await self.login():
            return []

        created_users = []
        for i in range(0, count, batch_size):
            batch_count = min(batch_size, count - i)
            tasks = [
                self.create_single_user(
                    days,
                    hours,
                    j + i,
                    message_limited,
                    rate_refresh_time,
                    message_bucket_sum,
                    message_bucket_time,
                )
                for j in range(batch_count)
            ]
            results = await tqdm.gather(
                *tasks,
                desc=f"Creating users (batch {i // batch_size + 1})",
                total=batch_count,
            )

            created_users.extend([r for r in results if r])

            if i + batch_size < count:
                await asyncio.sleep(1)

        return created_users

    async def create_redemption_code(self, points: int) -> Optional[Dict]:
        """Create a redemption code for ChatGPT points.

        Args:
            points: The number of points for the redemption code

        Returns:
            Optional[Dict]: Response data if successful, None if failed
        """
        if not self.token:
            await self.login()
            if not self.token:
                return None

        # Generate random code with points as prefix
        code = f"{points}-{str(uuid.uuid4()).replace('-', '')[:20]}"

        # Set expiration date to 10 years from now
        expire_time = (datetime.now() + timedelta(days=3650)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    # "https://gpthoutai.585dg.com/api/agent/codeAdd",
                    f"{self.base_url}/agent/codeAdd",
                    headers=self.headers,
                    params={"token": self.token},
                    data={
                        "code": code,
                        "bill": str(points),
                        "name": "chatgpt续费兑换码",
                        "description": "兑换额度后请点击渠道商店购买相应的套餐才能续费",
                        "time": expire_time,
                    },
                )
                response.raise_for_status()
                return {
                    "code": code,
                    "points": points,
                    "expire_time": expire_time,
                    "response": response.json(),
                }
            except Exception as e:
                logger.error(f"Failed to create redemption code: {str(e)}")
                return None

    async def batch_create_redemption_codes(
        self, points: int, count: int, batch_size: int = 5
    ) -> List[Dict]:
        """Batch create multiple redemption codes.

        Args:
            points: The number of points for each redemption code
            count: Number of codes to create
            batch_size: Number of codes to create in each batch

        Returns:
            List[Dict]: List of created redemption codes and their details
        """
        if not await self.login():
            return []

        created_codes = []
        for i in range(0, count, batch_size):
            batch_count = min(batch_size, count - i)
            tasks = [self.create_redemption_code(points) for _ in range(batch_count)]
            results = await tqdm.gather(
                *tasks,
                desc=f"Creating redemption codes (batch {i // batch_size + 1})",
                total=batch_count,
            )

            created_codes.extend([r for r in results if r])

            if i + batch_size < count:
                await asyncio.sleep(1)  # Add delay between batches

        return created_codes

    async def is_account_valid(self, account: str, password: str) -> bool:
        async with httpx.AsyncClient() as client:
            data = {"account": account, "password": password, "action": "default"}
            res = await client.post("https://chat.qqyunsd.com/login", json=data)
            logger.debug(res.cookies)
            if res.cookies:
                return True
            else:
                return False

    async def change_password(
        self, account: str, password: str, new_password: str
    ) -> bool:
        # 首先判断账号密码是否正确， 如果正确就修改， 否则不修改， 账号或者密码错误
        if await self.is_account_valid(account, password):
            pass
        else:
            return False

        # Get user info to retrieve user_id
        user_info = await self.get_user_info(account)
        logger.debug(f"User info: {user_info}")
        if not user_info or not user_info.get("data") or len(user_info["data"]) == 0:
            return False

        user_id = user_info["data"][0]["ID"]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/agent/editPassword",
                    headers=self.headers,
                    params={"token": self.token},
                    data={"user_id": user_id, "password": new_password},
                )
                response.raise_for_status()
                return True
            except Exception as e:
                print(f"Password change failed for user {account}: {str(e)}")
                return False


async def get_souruxgpt_manager():
    sorux_gpt_manager = SoruxGPTManager(admin_username, admin_password)
    await sorux_gpt_manager.login()
    return sorux_gpt_manager


def save_image_from_dict(data_dict):
    try:
        download_url = data_dict.get("download_url")
        if not download_url:
            return "错误: 字典中没有找到下载URL", False
        if data_dict.get("file_name"):
            file_name = Path(data_dict["file_name"]).name
        else:
            file_name = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        if "part" in file_name:
            return "中间图片，不保存", False
        response = requests.get(download_url)
        if response.status_code != 200:
            return f"错误: 下载失败，状态码 {response.status_code}", False
        # 计算图片内容的SHA-256哈希值
        content = response.content
        content_hash = hashlib.sha256(content).hexdigest()
        # 哈希记录文件路径
        hash_file = IMAGES_DIR / "image_hashes.json"
        # 加载现有哈希记录
        hash_map = {}
        if hash_file.exists():
            try:
                with open(hash_file, "r", encoding="utf-8") as f:
                    hash_map = json.load(f)
            except Exception as e:
                logger.error(f"读取哈希记录文件时出错: {str(e)}")
        # 检查是否已存在相同哈希值的图片
        if content_hash in hash_map:
            existing_file = hash_map[content_hash]
            if Path(IMAGES_DIR / existing_file).exists():
                logger.debug(f"图片已存在(哈希值相同): {existing_file}")
                return existing_file, False
        # 如果没有找到相同哈希值的图片，则保存新图片
        save_path = IMAGES_DIR / file_name
        with open(save_path, "wb") as f:
            f.write(content)

        # 更新哈希记录
        hash_map[content_hash] = file_name
        try:
            with open(hash_file, "w", encoding="utf-8") as f:
                json.dump(hash_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"更新哈希记录文件时出错: {str(e)}")

        logger.debug(f"图片已保存到: \n{save_path}")
        return file_name, True
    except Exception as e:
        return f"错误: {str(e)}", False


# Helper function to extract account from login request
def extract_account_from_request(request):
    return request.form["account"]


# Helper function to extract cookies
def extract_cookies(cookie_header):
    if not cookie_header:
        return {}
    cookies = {}
    parts = cookie_header.split("; ")
    for part in parts:
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name] = value
    return cookies


# Function to read JavaScript files
def read_js_file(filename):
    file_path = os.path.join(JS_DIR, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        # If file doesn't exist, create it with default content
        default_content = "// Default content for " + filename
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(default_content)
        return default_content


async def amain():
    from loguru import logger

    sorux_gpt_manager = SoruxGPTManager(admin_username, admin_password)
    await sorux_gpt_manager.login()
    user_info = await sorux_gpt_manager.get_user_info("98_1_f90173d55e3c")
    logger.debug(f"User info: {user_info}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(amain())
