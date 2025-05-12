import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from front_configs import *
import httpx
import streamlit as st
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
                    timeout=HTTP_TIMEOUT
                )
                # logger.debug(f"response:\n{response}")
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
                    timeout=HTTP_TIMEOUT

                )
                response.raise_for_status()
                return response.json()["UserID"]
            except Exception as e:
                logger.error(f"Registration failed for {username}: {str(e)}")
                from traceback import format_exc
                logger.error(format_exc())
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
                    timeout=HTTP_TIMEOUT

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
                    timeout=HTTP_TIMEOUT

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
                    timeout=HTTP_TIMEOUT

                )
                response.raise_for_status()
                return {"username": user_name, "success": True, "user_id": user_id}

        except Exception as e:
            return {"username": user_name, "success": False, "error": str(e)}

    async def batch_delete_users(self, user_names: List[str], batch_size: int = 50) -> List[Dict]:
        """Batch delete multiple users.

        Args:
            user_names: List of usernames to delete
            batch_size: Number of users to delete in each batch

        Returns:
            List[Dict]: List of deletion results for each user
        """
        if not await self.login():
            return [
                {"username": username, "success": False, "error": "Failed to login"}
                for username in user_names
            ]

        results = []
        for i in range(0, len(user_names), batch_size):
            try:
                batch_users = user_names[i:i+batch_size]
                batch_count = len(batch_users)
                
                tasks = [self.delete_user(user_name) for user_name in batch_users]
                batch_results = await tqdm.gather(
                    *tasks, 
                    desc=f"Deleting users (batch {i // batch_size + 1})", 
                    total=batch_count
                )
                
                results.extend(batch_results)
                logger.debug(f"finished: {len(results)}/{len(user_names)}")
                
                if i + batch_size < len(user_names):
                    await asyncio.sleep(1)
                await self.login()
            except:
                from traceback import format_exc
                logger.error(format_exc())
                await asyncio.sleep(10)
                await self.login()
                
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
                    timeout=HTTP_TIMEOUT

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
        batch_size: int = 50,
        message_limited: int = 5,
        rate_refresh_time: int = 1,
        message_bucket_sum: int = 100,
        message_bucket_time: int = 180,
    ) -> List[Dict]:
        if not await self.login():
            return []

        created_users = []
        for i in range(0, count, batch_size):
            try:

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
                logger.debug(f"finished: {len(created_users)}/{count}")
                if i + batch_size < count:
                    await asyncio.sleep(1)
                await self.login()
            except:
                from traceback import format_exc
                logger.error(format_exc())
                await asyncio.sleep(10)
                await self.login()


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
                    timeout=HTTP_TIMEOUT

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

class SoruxGPTManagerV2(SoruxGPTManager):

    """
    Only to rewrite the username generation and the add node logic.
    """

    def generate_credentials(self, days: int, hours: int = 0) -> tuple:
        def generate_uuid_string() -> str:
            # Generate UUID and remove hyphens, take first 12 characters
            return str(uuid.uuid4()).replace("-", "")[:12]

        days = max(days, 1)  # 至少为1
        # Format: liuli_days_randomstring
        username = f"ai_{days}_{generate_uuid_string()}"
        password = generate_uuid_string()
        return username, password

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

        node_added = await self.add_node(username, expire_time)
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

    async def add_node(self, user_id: str, expire_time: datetime) -> bool:
        """Override the add_node method to use the new API endpoint.

        Args:
            user_id: The username (in format liuli_days_randomstring)
            expire_time: Not used in this implementation

        Returns:
            bool: True if successful, False otherwise
        """
        async with httpx.AsyncClient() as client:
            try:
                headers = {"Content-Type": "application/json"}

                data = {
                    "username": user_id,  # The user_id parameter contains the username
                    "authkey": "92msdamidhx",  # Fixed verification key
                }

                response = await client.post(
                    "https://soruxgpt-liuli-usersystem.soruxgpt.com/api/add",
                    headers=headers,
                    json=data,
                    timeout=HTTP_TIMEOUT

                )
                response.raise_for_status()
                return True

            except Exception as e:
                logger.error(f"Add node failed for user {user_id}: {str(e)}")
                return False


async def create_sorux_accounts(
    key_number: int,
    total_hours: int,
    message_limited: int,
    rate_refresh_time: int,
    message_bucket_sum: int,
    message_bucket_time: int,
) -> List[Dict]:
    manager = SoruxGPTManager(admin_username, admin_password)
    days = total_hours // 24
    hours = total_hours % 24
    users = await manager.batch_create_users(
        count=key_number,
        days=days,
        hours=hours,
        message_limited=message_limited,
        rate_refresh_time=rate_refresh_time,
        message_bucket_sum=message_bucket_sum,
        message_bucket_time=message_bucket_time,
    )
    return users


async def create_sorux_accounts_v2(
    key_number: int,
    total_hours: int,
    message_limited: int,
    rate_refresh_time: int,
    message_bucket_sum: int,
    message_bucket_time: int,
) -> List[Dict]:
    manager = SoruxGPTManagerV2(admin_username, admin_password)
    days = total_hours // 24
    hours = total_hours % 24
    users = await manager.batch_create_users(
        count=key_number,
        days=days,
        hours=hours,
        message_limited=message_limited,
        rate_refresh_time=rate_refresh_time,
        message_bucket_sum=message_bucket_sum,
        message_bucket_time=message_bucket_time,
    )
    return users


async def delete_sorux_accounts(user_names: List[str]) -> bool:
    manager = SoruxGPTManager(admin_username, admin_password)
    return await manager.batch_delete_users(user_names)


async def parse_chatgpt_credentials(credentials: str) -> List[str]:
    """Parse ChatGPT credentials from formatted string.

    Format example:
    30_1_3a038b3a288c----30e92eb536cb
    30_1_039f8a3d1c7d----31d5d2fc26e7

    Returns:
        List[str]: List of usernames (e.g. ['30_1_3a038b3a288c', '30_1_039f8a3d1c7d'])
    """
    # Split by newlines and filter empty lines
    lines = [line.strip() for line in credentials.split("\n") if line.strip()]

    # Extract usernames (part before '----')
    usernames = []
    for line in lines:
        if "----" in line:
            username = line.split("----")[0].strip()
            usernames.append(username)

    return usernames


async def main():
    # Example usage
    manager = SoruxGPTManager(admin_username, admin_password)
    # Create accounts valid for 30 days
    print("Creating 30-day accounts:")
    users_30d = await manager.batch_create_users(count=2, days=30)
    for user in users_30d:
        print(user["formatted"])

    # Create accounts valid for 2 days and 12 hours
    print("\nCreating 2-day-12-hour accounts:")
    users_mixed = await manager.batch_create_users(count=2, days=2, hours=12)
    for user in users_mixed:
        print(user["formatted"])


async def delete_sorux_accounts_main():
    user_names = ["0_1_d42ae9aa9ecb", "30_1_039f8a3d1c7d"]
    res = await delete_sorux_accounts(user_names)
    logger.debug(res)


async def create_sorux_redemption_codes(points: int, code_number: int) -> List[Dict]:
    """Helper function to create redemption codes.

    Args:
        points: Points for each redemption code
        code_number: Number of codes to create

    Returns:
        List[Dict]: List of created redemption codes and their details
    """
    manager = SoruxGPTManager(admin_username, admin_password)
    codes = await manager.batch_create_redemption_codes(
        points=points, count=code_number
    )
    return codes


if __name__ == "__main__":
    asyncio.run(delete_sorux_accounts_main())
