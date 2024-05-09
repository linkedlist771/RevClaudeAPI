import redis
import uuid
from enum import Enum
from typing import Union, Tuple, List
from loguru import logger
from claude import Client
from tqdm import tqdm


class CookieKeyType(Enum):
    PLUS = "plus"
    BASIC = "basic"
    TEST = "test"


class CookieManager:

    def __init__(self, host="localhost", port=6379, db=11):
        """Initialize the connection to Redis."""
        self.redis = redis.StrictRedis(host=host, port=port, db=db)

    def get_cookie_type_key(self, cookie_key):
        return f"{cookie_key}:type"

    def get_cookie_account_key(self, cookie_key):
        return f"{cookie_key}:account"

    # 这里设置一下账号和cookie的type方便后面检索。

    # 暂时不设置过期时间，因为我也不知道过期时间是啥时候
    def upload_cookie(
        self, cookie: str, cookie_type=CookieKeyType.BASIC.value, account=""
    ):
        """Upload a new cookie with a specific expiration time."""
        cookie_key = f"cookie-{str(uuid.uuid4()).replace('-', '')}"
        self.redis.set(cookie_key, cookie)
        type_key = self.get_cookie_type_key(cookie_key)
        self.redis.set(type_key, cookie_type)
        account_key = self.get_cookie_account_key(cookie_key)
        self.redis.set(account_key, account)
        return cookie_key

    def update_cookie(self, cookie_key: str, cookie: str, account: str = ""):
        self.redis.set(cookie_key, cookie)
        account_key = self.get_cookie_account_key(cookie_key)
        self.redis.set(account_key, account)
        return f"Cookie {cookie_key} has been updated."

    def delete_cookie(self, cookie_key: str):
        """Delete a cookie."""
        self.redis.delete(cookie_key)
        type_key = self.get_cookie_type_key(cookie_key)
        self.redis.delete(type_key)
        account_key = self.get_cookie_account_key(cookie_key)
        self.redis.delete(account_key)
        return f"Cookie {cookie_key} has been deleted."

    def get_cookie_status(self, cookie_key: str):
        type_key = self.get_cookie_type_key(cookie_key)
        account_key = self.get_cookie_account_key(cookie_key)
        _type = self.redis.get(type_key)
        account = self.redis.get(account_key)
        return f"{cookie_key}: \n type: {_type} \n account: {account}"

    def get_all_cookies(self, cookie_type: str) -> list[str]:
        """Retrieve all cookies of a specified type."""
        pattern = f"*:type"
        cursor = 0
        cookies = []

        while True:
            cursor, keys = self.redis.scan(cursor, match=pattern, count=1000)
            for key in keys:
                actual_type = self.redis.get(key).decode("utf-8")
                if actual_type == cookie_type:
                    base_key = key.decode("utf-8").split(":type")[0]
                    cookie_value = self.redis.get(base_key)
                    if cookie_value:
                        cookies.append(cookie_value.decode("utf-8"))

            if cursor == 0:
                break

        return cookies

    def get_all_cookie_status(self):
        pattern = f"*:type"
        cursor = 0
        cookies = []

        while True:
            cursor, keys = self.redis.scan(cursor, match=pattern, count=1000)
            for key in keys:
                actual_type = self.redis.get(key).decode("utf-8")
                base_key = key.decode("utf-8").split(":type")[0]
                cookie_value = self.redis.get(base_key)
                account_key = self.get_cookie_account_key(base_key)
                account = self.redis.get(account_key)
                if cookie_value:
                    cookies.append(f"{base_key}: \n type: {actual_type} \n account: {account}")

            if cursor == 0:
                break

        return cookies

    # 还是重启一下比较好哎。
    def get_all_basic_and_plus_client(self) -> Tuple[List[Client], List[Client]]:
        _basic_cookies = self.get_all_cookies(CookieKeyType.BASIC.value)
        _plus_cookies = self.get_all_cookies(CookieKeyType.PLUS.value)
        _basic_clients = []
        _plus_clients = []

        logger.info("Begin register the client.....")
        for basic_cookie in tqdm(_basic_cookies):
            try:
                basic_client = Client(basic_cookie)
                _basic_clients.append(basic_client)
                logger.info(f"Register the basic client: {basic_client}")
            except Exception as e:
                logger.error(f"Failed to register the basic client: {e}")
        for plus_cookie in tqdm(_plus_cookies):
            try:
                plus_client = Client(plus_cookie)
                _plus_clients.append(plus_client)
                logger.info(f"Register the plus client: {plus_client}")
            except Exception as e:
                logger.error(f"Failed to register the plus client: {e}")
        return _basic_clients, _plus_clients

    def get_all_cookie_status(self):
        pattern = f"*:type"
        cursor = 0
        cookies = []

        while True:
            cursor, keys = self.redis.scan(cursor, match=pattern, count=1000)
            for key in keys:
                actual_type = self.redis.get(key).decode("utf-8")
                base_key = key.decode("utf-8").split(":type")[0]
                cookie_value = self.redis.get(base_key)
                account_key = self.get_cookie_account_key(base_key)
                account = self.redis.get(account_key)
                if cookie_value:
                    cookies.append(
                        f"{base_key}: \n type: {actual_type} \n account: {account}"
                    )

            if cursor == 0:
                break

        return cookies


def get_cookie_manager():
    return CookieManager()


# Example usage of the APIKeyManager
if __name__ == "__main__":
    manager = CookieManager()
    print(manager.upload_cookie("test_cookie", CookieKeyType.TEST.value))
