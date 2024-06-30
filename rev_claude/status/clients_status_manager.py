from uuid import uuid4

import redis
from enum import Enum
import time
from pydantic import BaseModel

from rev_claude.configs import REDIS_HOST


# from claude_cookie_manage import get_cookie_manager


def base62_encode(
    num, alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
):
    """Encode a number in Base62."""
    if num == 0:
        return alphabet[0]
    arr = []
    base = len(alphabet)
    while num:
        num, rem = divmod(num, base)
        arr.append(alphabet[rem])
    arr.reverse()
    return "".join(arr)


def get_short_uuid():
    # Generate a UUID
    uuid_num = uuid4().int
    # Take just a portion to keep it short, e.g., the last 9 digits, which reduces collision probability
    short_num = uuid_num % (62**6)
    # Encode this number in base62
    return base62_encode(short_num)


class ClientStatus(Enum):
    ACTIVE = "active"
    ERROR = "error"
    BUSY = "busy"
    CD = "cd"  # 等待刷新中。


class ClientsStatus(BaseModel):
    id: str
    status: str
    type: str
    idx: int
    message: str = ""


class ClientsStatusManager:

    def __init__(self, host=REDIS_HOST, port=6379, db=2):
        """Initialize the connection to Redis."""
        self.redis = redis.StrictRedis(
            host=host, port=port, db=db, decode_responses=True
        )
    def get_client_status_key(self, client_type, client_idx):
        return f"status-{client_type}-{client_idx}"

    def get_client_status_start_time_key(self, client_type, client_idx):
        return f"{self.get_client_status_key(client_type, client_idx)}:start_time"

    def get_limited_message(self, start_time, type, idx):
        # 获取账号状态
        client_status_key = self.get_client_status_key(type, idx)
        status = self.redis.get(client_status_key)
        if status == ClientStatus.ERROR.value:
            return "账号异常"

        current_time = time.time()
        # print(f"current_time: {current_time}, start_time: {start_time}")
        time_passed = current_time - float(start_time)
        remaining_time = 8 * 3600 - time_passed
        remaining_time = int(remaining_time)
        return f"还需等待{remaining_time}秒恢复使用。"

    def set_client_limited(self, client_type, client_idx, start_time):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        # 设置键值对
        client_status_start_time_key = self.get_client_status_start_time_key(
            client_type, client_idx
        )
        # 首先判断这个是不是已经是cd状态了。
        if self.redis.get(client_status_key) == ClientStatus.CD.value:
            return

        self.redis.set(client_status_key, ClientStatus.CD.value)
        self.redis.set(client_status_start_time_key, start_time)

    def set_client_error(self, client_type, client_idx):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        self.redis.set(client_status_key, ClientStatus.ERROR.value)

    def set_client_active(self, client_type, client_idx):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        self.redis.set(client_status_key, ClientStatus.ACTIVE.value)
        # client_status_start_time_key = self.get_client_status_start_time_key(client_type, client_idx

    def set_client_status(self, client_type, client_idx, status):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        self.redis.set(client_status_key, status)

    def set_client_active_when_cd(self, client_type, client_idx):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        status = self.redis.get(client_status_key)
        if status == ClientStatus.CD.value:
            client_status_start_time_key = self.get_client_status_start_time_key(
                client_type, client_idx
            )
            current_time = time.time()
            passed_time = current_time - float(
                self.redis.get(client_status_start_time_key)
            )
            if passed_time > 8 * 3600:
                self.redis.set(client_status_key, ClientStatus.ACTIVE.value)
                return True
            else:
                return False
        elif status == ClientStatus.ACTIVE.value:
            return True
        else:
            return False

    def create_if_not_exist(self, client_type, client_idx):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        if not self.redis.exists(client_status_key):
            self.redis.set(client_status_key, ClientStatus.ACTIVE.value)
            self.redis.set(
                self.get_client_status_start_time_key(client_type, client_idx),
                time.time(),
            )

    def get_all_clients_status(self, basic_clients, plus_clients):
        clients_status = []
        from rev_claude.cookie.claude_cookie_manage import get_cookie_manager

        cookie_manager = get_cookie_manager()
        for idx, client in basic_clients.items():
            # 首先判断这两个key是否存在？ 如果不存在， 就设置。
            self.create_if_not_exist("basic", idx)
            account = cookie_manager.get_account(client.cookie_key)
            is_active = self.set_client_active_when_cd("basic", idx)
            if is_active:
                _status = ClientStatus.ACTIVE.value
                _message = "可用"

            else:
                _status = ClientStatus.CD.value
                key = self.get_client_status_start_time_key("basic", idx)
                _message = self.get_limited_message(self.redis.get(key), "basic", idx)
            status = ClientsStatus(
                id=account,
                status=_status,
                type="normal",
                idx=idx,
                message=_message,
            )
            clients_status.append(status)
        for idx, client in plus_clients.items():
            account = cookie_manager.get_account(client.cookie_key)

            self.create_if_not_exist("plus", idx)
            is_active = self.set_client_active_when_cd("plus", idx)
            if is_active:
                _status = ClientStatus.ACTIVE.value
                _message = "可用"
            else:
                _status = ClientStatus.CD.value
                key = self.get_client_status_start_time_key("plus", idx)
                _message = self.get_limited_message(self.redis.get(key), "plus", idx)
            status = ClientsStatus(
                id=account,
                status=_status,
                type="plus",
                idx=idx,
                message=_message,
            )
            clients_status.append(status)

        return clients_status
