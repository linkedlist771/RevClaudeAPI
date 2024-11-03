import uuid
import httpx
import asyncio
from tqdm.asyncio import tqdm
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import streamlit as st
from front_configs import ADMIN_USERNAME, ADMIN_PASSWORD

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
                        # "message_limited": "5",
                        # "rate_refresh_time": "1",
                        # "message_bucket_sum": "40",
                        # "message_bucket_time": "180",
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

    # sorux_accounts = asyncio.run(create_sorux_accounts(key_number, total_hours,
    #                                                                 message_limited, rate_refresh_time, message_bucket_sum,
    #                                                                 message_bucket_time))


async def create_sorux_accounts(
    key_number: int,
    total_hours: int,
    message_limited: int,
    rate_refresh_time: int,
    message_bucket_sum: int,
    message_bucket_time: int,
) -> List[Dict]:
    manager = SoruxGPTManager("liuliu", "123.liu")
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


def check_password():
    """Returns `True` if the user had the correct password."""

    # 创建一个组件来执行JavaScript代码
    st.components.v1.html("""
        <script>
            function checkLoginStatus() {
                const username = localStorage.getItem('username');
                const loginStatus = localStorage.getItem('loginStatus');
                if (username && loginStatus === 'true') {
                    window.parent.postMessage({type: 'LOGIN_STATUS', username: username}, '*');
                }
            }

            function setLoginStatus(username) {
                localStorage.setItem('username', username);
                localStorage.setItem('loginStatus', 'true');
            }

            function clearLoginStatus() {
                localStorage.removeItem('username');
                localStorage.removeItem('loginStatus');
            }

            // 检查登录状态
            checkLoginStatus();
        </script>
    """, height=0)

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] == ADMIN_USERNAME and st.session_state["password"] == ADMIN_PASSWORD:
            st.session_state["password_correct"] = True
            # 设置登录状态到localStorage
            st.components.v1.html(f"""
                <script>
                    setLoginStatus('{st.session_state["username"]}');
                </script>
            """, height=0)
            del st.session_state["password"]  # 不存储密码
        else:
            st.session_state["password_correct"] = False
            # 清除登录状态
            st.components.v1.html("""
                <script>
                    clearLoginStatus();
                </script>
            """, height=0)
            if "username" in st.session_state:
                del st.session_state["username"]

    # 通过JavaScript检查localStorage中的登录状态
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        # 显示登录界面
        st.text_input("用户名", key="username")
        st.text_input("密码", type="password", key="password")
        st.button("登录", on_click=password_entered)
        if "password" in st.session_state and st.session_state["password"]:  # 如果有登录尝试
            st.error("😕 用户名或密码错误")
        return False
    else:
        # 密码正确
        return True


async def main():
    # Example usage
    manager = SoruxGPTManager("liuliu", "123.liu")
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


if __name__ == "__main__":
    asyncio.run(main())
