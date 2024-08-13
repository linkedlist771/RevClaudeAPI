import asyncio
import redis
from redis.asyncio import Redis
import uuid
from enum import Enum
from typing import Tuple, List
from loguru import logger
import random
from rev_claude.client.claude import Client
from rev_claude.configs import REDIS_HOST, REDIS_PORT
from rev_claude.utils.async_utils import register_clients


class CookieKeyType(Enum):
    PLUS = "plus"
    BASIC = "basic"
    TEST = "test"
    NORMAL = "normal"


class CookieUsageType(Enum):
    WEB_LOGIN_ONLY = 0
    REVERSE_API_ONLY = 1
    BOTH = 2

    @classmethod
    def get_default(cls):
        if random.random() < 0.2:
            return cls.REVERSE_API_ONLY
        else:
            return cls.WEB_LOGIN_ONLY

    @classmethod
    def from_redis_value(cls, value):
        if value is None:
            return cls.get_default()
        return cls(int(value))


class CookieManager:

    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, db=1):
        """Initialize the connection to Redis."""
        self.host = host
        self.port = port
        self.db = db
        self.aioredis = None

    async def get_aioredis(self):
        if self.aioredis is None:
            self.aioredis = await Redis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}"
            )
        return self.aioredis

    async def decoded_get(self, key):
        res = await (await self.get_aioredis()).get(key)
        if isinstance(res, bytes):
            res = res.decode("utf-8")
        return res

    def get_cookie_type_key(self, cookie_key):
        return f"{cookie_key}:type"

    def get_cookie_account_key(self, cookie_key):
        return f"{cookie_key}:account"

    def get_cookie_organization_key(self, cookie_key):
        return f"{cookie_key}:organization"

    def get_cookie_usage_type_key(self, cookie_key):
        return f"{cookie_key}:usage_type"

    async def get_cookie_usage_type(self, cookie_key: str) -> CookieUsageType:
        """Retrieve the usage type for a specific cookie."""
        usage_type_key = self.get_cookie_usage_type_key(cookie_key)
        usage_type_value = await self.decoded_get(usage_type_key)

        if usage_type_value is None:
            return CookieUsageType.get_default()

        if isinstance(usage_type_value, bytes):
            usage_type_value = usage_type_value.decode("utf-8")

        try:
            return CookieUsageType(int(usage_type_value))
        except ValueError:
            logger.warning(
                f"Invalid usage type value for cookie {cookie_key}: {usage_type_value}"
            )
            return CookieUsageType.get_default()

    async def set_cookie_usage_type(self, cookie_key: str, usage_type: CookieUsageType):
        """Set the usage type for a specific cookie."""
        usage_type_key = self.get_cookie_usage_type_key(cookie_key)
        await (await self.get_aioredis()).set(usage_type_key, usage_type.value)
        return f"Usage type for {cookie_key} has been set to {usage_type.value}."

    async def update_organization_id(self, cookie_key, organization_id):
        organization_key = self.get_cookie_organization_key(cookie_key)
        redis_instance = await self.get_aioredis()
        await redis_instance.set(organization_key, organization_id)
        return f"Organization ID for {cookie_key} has been updated."

    async def delete_organization_id(self, cookie_key):
        organization_key = self.get_cookie_organization_key(cookie_key)
        redis_instance = await self.get_aioredis()
        if await redis_instance.exists(organization_key):
            await redis_instance.delete(organization_key)
            return f"Organization ID for {cookie_key} has been deleted."
        else:
            return f"No organization found for {cookie_key}. Nothing to delete."

    async def get_organization_id(self, cookie_key):
        organization_key = self.get_cookie_organization_key(cookie_key)
        redis_instance = await self.get_aioredis()
        organization_id = await redis_instance.get(organization_key)
        logger.debug(f"organization_id from redis: {organization_id}")
        if organization_id is None:
            return None
        return organization_id.decode("utf-8") if isinstance(organization_id, bytes) else organization_id
    async def upload_cookie(
        self, cookie: str, cookie_type=CookieKeyType.BASIC.value, account=""
    ):
        """Upload a new cookie with a specific expiration time."""
        cookie_key = f"cookie-{str(uuid.uuid4()).replace('-', '')}"
        redis_instance = await self.get_aioredis()
        await redis_instance.set(cookie_key, cookie)
        type_key = self.get_cookie_type_key(cookie_key)
        await redis_instance.set(type_key, cookie_type)
        account_key = self.get_cookie_account_key(cookie_key)
        await redis_instance.set(account_key, account)
        return cookie_key

    async def update_cookie(self, cookie_key: str, cookie: str, account: str = ""):
        account_key = self.get_cookie_account_key(cookie_key)
        redis_instance = await self.get_aioredis()
        await redis_instance.set(cookie_key, cookie)
        await redis_instance.set(account_key, account)
        return f"Cookie {cookie_key} has been updated."

    async def delete_cookie(self, cookie_key: str):
        """Delete a cookie."""
        type_key = self.get_cookie_type_key(cookie_key)
        account_key = self.get_cookie_account_key(cookie_key)
        redis_instance = await self.get_aioredis()
        await redis_instance.delete(cookie_key)
        await redis_instance.delete(type_key)
        await redis_instance.delete(account_key)
        return f"Cookie {cookie_key} has been deleted."

    async def get_cookie_status(self, cookie_key: str):
        type_key = self.get_cookie_type_key(cookie_key)
        account_key = self.get_cookie_account_key(cookie_key)
        _type = await self.decoded_get(type_key)
        account = await self.decoded_get(account_key)
        usage_type = await self.get_cookie_usage_type(cookie_key)
        return {
            "cookie_key": cookie_key,
            "type": _type,
            "account": account,
            "usage_type": usage_type.value,
        }

    async def get_account(self, cookie_key: str):
        account_key = self.get_cookie_account_key(cookie_key)
        redis_instance = await self.get_aioredis()
        account = await redis_instance.get(account_key)
        account = account.decode("utf-8")
        return account

    async def get_all_cookies(self, cookie_type: str):
        """Retrieve all cookies of a specified type."""
        pattern = f"*:type"
        cursor = 0
        cookies = []
        cookies_keys = []
        redis_instance = await self.get_aioredis()
        while True:
            cursor, keys = await redis_instance.scan(cursor, match=pattern, count=1000)
            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode("utf-8")
                actual_type = await self.decoded_get(key)
                if actual_type == cookie_type:
                    base_key = key.split(":type")[0]
                    cookie_value = await self.decoded_get(base_key)
                    if cookie_value:
                        cookies.append(cookie_value)
                        cookies_keys.append(base_key)

            if cursor == 0:
                break

        return cookies, cookies_keys

    async def get_all_cookie_status(self):
        pattern = f"*:type"
        cursor = 0
        cookies = []
        redis_instance = await self.get_aioredis()
        while True:
            cursor, keys = await redis_instance.scan(cursor, match=pattern, count=1000)
            for key in keys:
                actual_type = await self.decoded_get(key)
                if isinstance(key, bytes):
                    key = key.decode("utf-8")
                base_key = key.split(":type")[0]
                cookie_value = await self.decoded_get(base_key)
                account_key = self.get_cookie_account_key(base_key)
                account = await self.decoded_get(account_key)
                if cookie_value:
                    cookies.append(
                        {
                            "cookie": cookie_value,
                            "type": actual_type,
                            "account": account,
                        }
                    )

            if cursor == 0:
                break

        return cookies

    async def get_all_basic_and_plus_client(
        self, reload: bool = False
    ) -> Tuple[List[Client], List[Client]]:
        _basic_cookies, _basic_cookie_keys = await self.get_all_cookies(
            CookieKeyType.BASIC.value
        )
        _plus_cookies, _plus_cookie_keys = await self.get_all_cookies(
            CookieKeyType.PLUS.value
        )
        _basic_clients, _plus_clients = await register_clients(
            _basic_cookies, _basic_cookie_keys, _plus_cookies, _plus_cookie_keys, reload
        )

        return _basic_clients, _plus_clients


def get_cookie_manager():
    return CookieManager()


if __name__ == "__main__":
    manager = CookieManager()
    print(manager.upload_cookie("test_cookie", CookieKeyType.TEST.value))
