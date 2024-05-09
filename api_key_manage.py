import time

import redis
import uuid
from enum import Enum
from loguru import logger
from utility import get_current_time
from configs import (
    BASIC_KEY_MAX_USAGE,
    PLUS_KEY_MAX_USAGE,
    API_KEY_REFRESH_INTERVAL,
    API_KEY_REFRESH_INTERVAL_HOURS,
)


class APIKeyType(Enum):
    PLUS = "plus"
    BASIC = "basic"


class APIKeyManager:
    def __init__(self, host="localhost", port=6379, db=10):
        """Initialize the connection to Redis."""
        self.redis = redis.StrictRedis(
            host=host, port=port, db=db, decode_responses=True
        )

    def create_api_key(self, expiration_seconds, api_key_type=APIKeyType.BASIC.value):
        """Create a new API key with a specific expiration time."""
        if isinstance(api_key_type, bytes):
            api_key_type = api_key_type.decode("utf-8")
        api_key = f"sj-{str(uuid.uuid4()).replace('-', '')}"
        self.redis.setex(api_key, expiration_seconds, "active")
        self.redis.setex(f"{api_key}:usage", expiration_seconds, 0)
        self.redis.setex(f"{api_key}:type", expiration_seconds, api_key_type)
        return api_key

    def is_api_key_valid(self, api_key):
        """Check if an API key is still valid (exists and has not expired)."""
        return self.redis.exists(api_key) == 1

    def increment_usage(self, api_key):
        """Increment the usage count for a given API key."""
        usage_key = f"{api_key}:usage"
        self.redis.incr(usage_key)
        current_usage_key = f"{api_key}:current_usage"
        self.redis.incr(current_usage_key)
        return (
            f"Usage count for API key {api_key} has been incremented.:\n"
            f"usage: {self.get_usage(api_key)}\n"
            f"current_usage: {self.get_current_usage(api_key)}"
        )

    def get_usage(self, api_key):
        """Retrieve the current usage count of an API key."""
        usage_key = f"{api_key}:usage"
        count = self.redis.get(usage_key)
        return int(count) if count else 0

    def get_current_usage(self, api_key):
        current_usage_key = f"{api_key}:current_usage"
        current_usage = self.redis.get(current_usage_key)
        if current_usage is None:
            self.redis.set(current_usage_key, 0)
            return 0
        return int(current_usage)

    def get_last_usage_time(self, api_key):
        """Retrieve the last usage time of an API key."""
        last_usage_time_key = f"{api_key}:last_usage_time"
        last_usage_time = self.redis.get(last_usage_time_key)
        #
        if last_usage_time is None:
            # If the key does not exist, set it to the current timestamp
            current_timestamp = get_current_time()
            self.redis.set(last_usage_time_key, current_timestamp)
            return current_timestamp
        else:
            # If the key exists, return the value
            return int(last_usage_time)

    def has_exceeded_limit(self, api_key) -> bool:
        current_usage = self.get_current_usage(api_key)
        key_type = self.get_api_key_type(api_key)
        if key_type == APIKeyType.BASIC.value:
            usage_limit = BASIC_KEY_MAX_USAGE
        else:
            usage_limit = PLUS_KEY_MAX_USAGE
        if current_usage >= usage_limit:
            # 判断当前时间和上次使用时间的时间差
            last_usage_time = self.get_last_usage_time(api_key)
            current_timestamp = get_current_time()
            time_diff = current_timestamp - last_usage_time
            if time_diff < API_KEY_REFRESH_INTERVAL:
                return True
            else:
                # 超过时间间隔，重置当前使用次数
                self.redis.set(f"{api_key}:current_usage", 0)
                # 重置当前的使用时间
                self.redis.set(f"{api_key}:last_usage_time", current_timestamp)
                return False

        else:
            return False

    def generate_exceed_message(self, api_key) -> str:
        key_type = self.get_api_key_type(api_key)
        if key_type == APIKeyType.BASIC.value:
            usage_limit = BASIC_KEY_MAX_USAGE
        else:
            usage_limit = PLUS_KEY_MAX_USAGE
        last_usage_time = self.get_last_usage_time(api_key)
        current_timestamp = get_current_time()
        time_diff = current_timestamp - last_usage_time
        wait_time = max(0, API_KEY_REFRESH_INTERVAL - time_diff)  # 确保不显示负数

        message = (
            f"You api key is the {key_type} type, the usage limit is {usage_limit} times / {API_KEY_REFRESH_INTERVAL_HOURS} hours"
            f"You need to wait {wait_time} seconds to use it again."
            f"您的API密钥是{key_type}类型，使用限制是{usage_limit}次/{API_KEY_REFRESH_INTERVAL_HOURS}小时"
            f"您需要等待{wait_time}秒后再次使用。"
        )
        return message

    # 这里设置还是用普通的字符串算了。
    def get_api_key_type(self, api_key):
        """Retrieve the status of an API key."""
        type_key = f"{api_key}:type"
        _type = self.redis.get(type_key)
        return _type if _type else APIKeyType.BASIC.value

    def is_plus_user(self, api_key) -> bool:
        key_type = self.get_api_key_type(api_key)
        logger.info(f"key_type: {key_type}")
        return key_type == APIKeyType.PLUS.value
        # return self.get_api_key_type(api_key) == APIKeyType.PLUS.value

    def set_api_key_type(self, api_key, _type):
        """Set the status of an API key."""
        type_key = f"{api_key}:type"
        if isinstance(_type, bytes):
            _type = _type.decode("utf-8")
        self.redis.set(type_key, _type)
        return f"API key {api_key} is now a {_type} user."

    def delete_api_key(self, api_key):
        """Delete an API key and its associated usage count."""
        usage_key = f"{api_key}:usage"
        # Pipeline the delete operations to ensure both keys are deleted together
        pipeline = self.redis.pipeline()
        pipeline.delete(api_key)
        pipeline.delete(usage_key)
        pipeline.execute()

    def add_api_key(
        self, api_key, expiration_seconds, api_key_type=APIKeyType.BASIC.value
    ):
        """Add an existing API key with a specific expiration time."""
        self.redis.setex(api_key, expiration_seconds, "active")
        self.redis.setex(f"{api_key}:usage", expiration_seconds, 0)
        self.redis.setex(f"{api_key}:type", expiration_seconds, api_key_type)
        return api_key

    def list_active_api_keys(self):
        """List all active API keys."""
        active_keys = []
        for key in self.redis.scan_iter("sj-*"):  # Assuming all keys start with 'sj-'
            if self.redis.ttl(key) > 0:  # Check if the key has not expired
                active_keys.append(key)
        return active_keys

    def get_apikey_information(self, api_key):
        usage = self.get_usage(api_key)
        current_usage = self.get_current_usage(api_key)
        last_usage_time = self.get_last_usage_time(api_key)
        key_type = self.get_api_key_type(api_key)
        # expire time
        expire_time = self.redis.ttl(api_key)
        # turn the last_usage_time to a readable format: time step => time
        if last_usage_time is not None:
            last_usage_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_usage_time))
        else:
            last_usage_time = 'Never used'
        if expire_time == -1:
            expire_time = 'Never expire'
        else:
            expire_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + expire_time))
        return {
            "usage": usage,
            "current_usage": current_usage,
            "last_usage_time": last_usage_time,
            "key_type": key_type,
            "expire_time": expire_time,
        }


def get_api_key_manager():
    return APIKeyManager()


# Example usage of the APIKeyManager
if __name__ == "__main__":
    manager = APIKeyManager()
    key = manager.create_api_key(300)
    print("API Key:", key)
    print("Key Valid:", manager.is_api_key_valid(key))
    manager.increment_usage(key)
    manager.increment_usage(key)
    print("Usage Count:", manager.get_usage(key))
    manager.delete_api_key(key)
    print("Key Valid after deletion:", manager.is_api_key_valid(key))
