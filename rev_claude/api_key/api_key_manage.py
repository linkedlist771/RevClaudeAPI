import time
from datetime import datetime, timedelta

import redis
from redis.asyncio import Redis
import uuid
from enum import Enum
from loguru import logger
from redis.asyncio.utils import pipeline

from front_python.front_manager import api_key_info, expiration_days
from rev_claude.utility import get_current_time
from rev_claude.configs import (
    BASIC_KEY_MAX_USAGE,
    PLUS_KEY_MAX_USAGE,
    API_KEY_REFRESH_INTERVAL,
    API_KEY_REFRESH_INTERVAL_HOURS,
    REDIS_HOST,
    REDIS_PORT,
    ACCOUNT_DELETE_LIMIT,
)


class APIKeyType(Enum):
    PLUS = "plus"
    BASIC = "basic"


class APIKeyManager:
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, db=0):
        """Initialize the connection to Redis."""
        # self.redis = redis.StrictRedis(
        #     host=host, port=port, db=db, decode_responses=True
        # )
        """Initialize the connection to Redis."""
        self.host = host
        self.port = port
        self.db = db
        self.aioredis = None

    async def get_aioredis(self):
        if self.aioredis is None:
            self.aioredis = await Redis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}", decode_responses=True
            )
        return self.aioredis

    async def decoded_get(self, key):
        res = await (await self.get_aioredis()).get(key)
        if isinstance(res, bytes):
            res = res.decode("utf-8")
        return res

    async def set_async(self, key, value):
        await (await self.get_aioredis()).set(key, value)

    async def setex_async(self, key, expiration, value):
        await (await self.get_aioredis()).setex(key, expiration, value)

    async def exists_async(self, key):
        return await (await self.get_aioredis()).exists(key)

    async def delete_async(self, key):
        await (await self.get_aioredis()).delete(key)

    async def incrby_async(self, key, increment):
        await (await self.get_aioredis()).incrby(key, increment)

    async def scan_iter_async(self, pattern):
        return await (await self.get_aioredis()).scan_iter(pattern)

    async def ttl_async(self, key):
        return await (await self.get_aioredis()).ttl(key)

    async def get_pipeline(self):
        return (await  self.get_aioredis()).pipeline()

    async def create_api_key(
        self, expiration_seconds, api_key_type=APIKeyType.BASIC.value
    ):
        """Create a new API key with a specific expiration time."""
        if isinstance(api_key_type, bytes):
            api_key_type = api_key_type.decode("utf-8")
        api_key = f"sj-{str(uuid.uuid4()).replace('-', '')}"
        # self.redis.set(f"{api_key}:usage", 0)
        # self.redis.set(f"{api_key}:type", api_key_type)
        # self.redis.set(f"{api_key}:expiration", expiration_seconds)
        # self.redis.set(api_key, "active")
        await self.set_async(f"{api_key}:usage", 0)
        await self.set_async(f"{api_key}:type", api_key_type)
        await self.set_async(f"{api_key}:expiration", expiration_seconds)
        await self.set_async(api_key, "active")

        return api_key

    async def activate_api_key(self, api_key):
        # 首先判断是否存在
        if not (await self.is_api_key_valid(api_key)):
            return "不存在该APIKEY"
        # 判断是否已经激活
        # ttl = self.redis.ttl(api_key)
        ttl = await self.ttl_async(api_key)
        if ttl == -1:
            # 还未激活
            # expiration_seconds = int(
            #     self.redis.get(f"{api_key}:expiration")
            # )  # 确保转换为整数
            expiration_seconds = int(await (self.decoded_get(f"{api_key}:expiration")))

            # api_key_type = self.redis.get(f"{api_key}:type")
            api_key_type = await self.decoded_get(f"{api_key}:type")
            if isinstance(api_key_type, bytes):
                api_key_type = api_key_type.decode("utf-8")
            # self.redis.setex(api_key, expiration_seconds, "active")
            # self.redis.setex(f"{api_key}:usage", expiration_seconds, 0)
            # self.redis.setex(f"{api_key}:type", expiration_seconds, api_key_type)
            await self.setex_async(api_key, expiration_seconds, "active")
            await self.setex_async(f"{api_key}:usage", expiration_seconds, 0)
            await self.setex_async(f"{api_key}:type", expiration_seconds, api_key_type)

            return f"API key {api_key} has been activated."
        elif ttl == -2:
            return "APIKEY已经过期"
        else:
            return f"APIKEY已经激活, 还有{ttl}秒过期"

    async def is_api_key_valid(self, api_key):
        """Check if an API key is still valid (exists and has not expired)."""
        # return self.redis.exists(api_key) == 1
        return await self.exists_async(api_key)

    async def increment_usage(self, api_key, increment=1):
        """Increment the usage count for a given API key."""
        usage_key = f"{api_key}:usage"
        current_usage_key = f"{api_key}:current_usage"

        # 执行增量操作
        await self.incrby_async(usage_key, increment)
        await self.incrby_async(current_usage_key, increment)

        # 获取更新后的使用次数
        usage = await self.get_usage(api_key)
        current_usage = await self.get_current_usage(api_key)

        # 构建并返回结果字符串
        return (
            f"Usage count for API key {api_key} has been incremented:\n"
            f"usage: {usage}\n"
            f"current_usage: {current_usage}"
        )

    async def get_usage(self, api_key):
        """Retrieve the current usage count of an API key."""
        usage_key = f"{api_key}:usage"
        # count = self.redis.get(usage_key)
        count = await self.decoded_get(usage_key)
        return int(count) if count else 0

    async def get_current_usage(self, api_key):
        current_usage_key = f"{api_key}:current_usage"
        # current_usage = self.redis.get(current_usage_key)
        current_usage = await self.decoded_get(current_usage_key)
        if current_usage is None:
            # self.redis.set(current_usage_key, 0)
            await self.set_async(current_usage_key, 0)
            return 0

        last_usage_time = await self.get_last_usage_time(api_key)
        current_time = get_current_time()
        time_diff = current_time - last_usage_time
        if time_diff >= API_KEY_REFRESH_INTERVAL:
            # self.redis.set(current_usage_key, 0)
            # self.redis.set(f"{api_key}:last_usage_time", current_time)
            await self.set_async(current_usage_key, 0)
            await self.set_async(f"{api_key}:last_usage_time", current_time)
            current_usage = 0

        return int(current_usage)

    async def get_last_usage_time(self, api_key):
        """Retrieve the last usage time of an API key."""
        last_usage_time_key = f"{api_key}:last_usage_time"
        # last_usage_time = self.redis.get(last_usage_time_key)
        last_usage_time = await self.decoded_get(last_usage_time_key)
        #
        if last_usage_time is None:
            # If the key does not exist, set it to the current timestamp
            current_timestamp = get_current_time()
            # self.redis.set(last_usage_time_key, current_timestamp)
            await self.set_async(last_usage_time_key, current_timestamp)
            return current_timestamp
        else:
            # If the key exists, return the value
            return int(last_usage_time)

    async def has_exceeded_limit(self, api_key) -> bool:
        current_usage = await self.get_current_usage(api_key)
        # 首先检测是不是超过限制进行帅脚本了
        if current_usage >= ACCOUNT_DELETE_LIMIT:
            # self.redis.delete(api_key)
            await self.delete_async(api_key)
            return True

        key_type = await self.get_api_key_type(api_key)
        if key_type == APIKeyType.BASIC.value:
            usage_limit = BASIC_KEY_MAX_USAGE
        else:
            usage_limit = PLUS_KEY_MAX_USAGE
        if current_usage >= usage_limit:
            # 判断当前时间和上次使用时间的时间差
            last_usage_time = await self.get_last_usage_time(api_key)
            current_timestamp = get_current_time()
            time_diff = current_timestamp - last_usage_time
            if time_diff < API_KEY_REFRESH_INTERVAL:
                return True
            else:
                # # 超过时间间隔，重置当前使用次数
                # self.redis.set(f"{api_key}:current_usage", 0)
                # # 重置当前的使用时间
                # self.redis.set(f"{api_key}:last_usage_time", current_timestamp)
                await self.set_async(f"{api_key}:current_usage", 0)
                await self.set_async(f"{api_key}:last_usage_time", current_timestamp)
                return False

        else:
            return False

    async def generate_exceed_message(self, api_key) -> str:
        key_type = await self.get_api_key_type(api_key)
        if key_type == APIKeyType.BASIC.value:
            usage_limit = BASIC_KEY_MAX_USAGE
        else:
            usage_limit = PLUS_KEY_MAX_USAGE
        last_usage_time = await self.get_last_usage_time(api_key)
        current_timestamp = get_current_time()
        time_diff = current_timestamp - last_usage_time
        wait_time = max(0, API_KEY_REFRESH_INTERVAL - time_diff)  # 确保不显示负数

        current_time = datetime.now()
        next_usage_time = current_time + timedelta(seconds=wait_time)

        message = (
            f"您的账户是{key_type}类型，使用限制是{usage_limit}次/{API_KEY_REFRESH_INTERVAL_HOURS}小时。"
            f"您可以在 {next_usage_time.strftime('%H:%M:%S')} 后再次使用。"
        )
        return message

    # 这里设置还是用普通的字符串算了。
    async def get_api_key_type(self, api_key):
        """Retrieve the status of an API key."""
        type_key = f"{api_key}:type"
        # _type = self.redis.get(type_key)
        _type = await self.decoded_get(type_key)
        return _type if _type else APIKeyType.BASIC.value

    async def is_plus_user(self, api_key) -> bool:
        # key_type = self.get_api_key_type(api_key)
        key_type = await self.get_api_key_type(api_key)
        logger.info(f"key_type: {key_type}")
        return key_type == APIKeyType.PLUS.value
        # return self.get_api_key_type(api_key) == APIKeyType.PLUS.value

    async def set_api_key_type(self, api_key, _type):
        """Set the status of an API key."""
        type_key = f"{api_key}:type"
        if isinstance(_type, bytes):
            _type = _type.decode("utf-8")
        # self.redis.set(type_key, _type)
        await self.set_async(type_key, _type)
        return f"API key {api_key} is now a {_type} user."

    async def reset_current_usage(self, api_key):
        """Reset the current usage count of an API key."""
        current_usage_key = f"{api_key}:current_usage"
        # self.redis.set(current_usage_key, 0)
        await self.set_async(current_usage_key, 0)
        return await self.get_current_usage(api_key)

    def get_associated_keys(self, api_key):
        """获取与API密钥相关联的所有键。"""
        return [
            api_key,
            f"{api_key}:usage",
            f"{api_key}:type",
            f"{api_key}:expiration",
            f"{api_key}:current_usage",
            f"{api_key}:last_usage_time",
        ]

    async def delete_api_key(self, api_key):
        """删除单个API密钥及其所有关联数据。"""
        keys_to_delete = self.get_associated_keys(api_key)
        # deleted_count = self.redis.delete(*keys_to_delete)
        deleted_count = await self.delete_async(*keys_to_delete)
        return f"已删除{deleted_count}个与API密钥相关的键。"

    async def batch_delete_api_keys(self, api_keys: list[str]):
        """批量删除多个API密钥及其所有关联数据。"""
        all_keys_to_delete = []
        for api_key in api_keys:
            all_keys_to_delete.extend(self.get_associated_keys(api_key))

        # deleted_count = self.redis.delete(*all_keys_to_delete)
        deleted_count = await self.delete_async(*all_keys_to_delete)
        return f"已删除{deleted_count}个与{len(api_keys)}个API密钥相关的键。"

    async def add_api_key(
        self, api_key, expiration_seconds, api_key_type=APIKeyType.BASIC.value
    ):
        """Add an existing API key with a specific expiration time."""
        # self.redis.setex(api_key, expiration_seconds, "active")
        # self.redis.setex(f"{api_key}:usage", expiration_seconds, 0)
        # self.redis.setex(f"{api_key}:type", expiration_seconds, api_key_type)
        await self.setex_async(api_key, expiration_seconds, "active")
        await self.setex_async(f"{api_key}:usage", expiration_seconds, 0)
        await self.setex_async(f"{api_key}:type", expiration_seconds, api_key_type)
        return f"API key {api_key} has been added."

    async def list_active_api_keys(self):
        """List all active API keys."""
        active_keys = []
        # for key in self.redis.scan_iter("sj-*"):  # Assuming all keys start with 'sj-'
        scan_res = await self.scan_iter_async("sj-*")
        # async for key in self.scan_iter_async("sj-*"):  # Assuming all keys start with 'sj-'
        for key in scan_res:
            # ttl = await self.redis.ttl(key)
            ttl = await self.ttl_async(key)
            if ttl > 0:  # Check if the key has not expired
                active_keys.append(key)
        return active_keys

    async def get_apikey_information(self, api_key):
        usage = await self.get_usage(api_key)
        current_usage = await self.get_current_usage(api_key)
        last_usage_time = await self.get_last_usage_time(api_key)
        key_type = await self.get_api_key_type(api_key)

        # BASIC_KEY_MAX_USAGE
        # PLUS_KEY_MAX_USAGE
        usage_limit = (
            BASIC_KEY_MAX_USAGE
            if key_type == APIKeyType.BASIC.value
            else PLUS_KEY_MAX_USAGE
        )
        # expire_time = self.redis.ttl(api_key)
        expire_time = await self.ttl_async(api_key)
        # turn the last_usage_time to a readable format: time step => time
        is_key_valid = True
        if last_usage_time is not None:
            last_usage_time = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(last_usage_time)
            )
        else:
            last_usage_time = "Never used"
        if expire_time == -1:
            expire_time = "Never expire"
        elif expire_time == -2:
            expire_time = "Key does not exist or has expired"
            is_key_valid = False
        else:
            expire_time = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(time.time() + expire_time)
            )
        return {
            "usage": usage,
            "current_usage": current_usage,
            "last_usage_time": last_usage_time,
            "key_type": key_type,
            "expire_time": expire_time,
            "is_key_valid": is_key_valid,
            "usage_limit": usage_limit,
        }

    async def extend_api_key_expiration(self, api_key, additional_days):
        """延长API密钥的过期时间。"""
        if not (await self.is_api_key_valid(api_key)):
            return f"API密钥 {api_key} 无效或已过期。"

        # 将天数转换为秒数
        additional_seconds = additional_days * 24 * 60 * 60

        # 获取当前的TTL
        # current_ttl = self.redis.ttl(api_key)
        current_ttl = await self.ttl_async(api_key)

        if current_ttl == -1:  # 密钥存在但没有过期时间
            new_ttl = additional_seconds
        elif current_ttl > 0:
            new_ttl = current_ttl + additional_seconds
        else:
            return f"API密钥 {api_key} 已经过期，无法延长。"

        # 延长主密钥和所有关联密钥的过期时间
        # pipeline = self.redis.pipeline()
        # for key in self.get_associated_keys(api_key):
        #     pipeline.expire(key, new_ttl)
        __pipeline = await self.get_pipeline()
        for key in self.get_associated_keys(api_key):
            await __pipeline.expire(key, new_ttl)
        await __pipeline.execute()

        new_expiration_days = new_ttl / (24 * 60 * 60)
        return f"API密钥 {api_key} 的过期时间已延长 {additional_days} 天。新的过期时间还剩 {new_expiration_days:.2f} 天。"


def get_api_key_manager():
    return APIKeyManager()


# Example usage of the APIKeyManager
if __name__ == "__main__":
    manager = APIKeyManager()
