from uuid import uuid4

import redis
from enum import Enum
import time
from pydantic import BaseModel


def base62_encode(num, alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'):
    """Encode a number in Base62."""
    if num == 0:
        return alphabet[0]
    arr = []
    base = len(alphabet)
    while num:
        num, rem = divmod(num, base)
        arr.append(alphabet[rem])
    arr.reverse()
    return ''.join(arr)

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

    def __init__(self, host="localhost", port=6379, db=2):
        """Initialize the connection to Redis."""
        self.redis = redis.StrictRedis(host=host, port=port, db=db, decode_responses=True)


    # 8 小时刷新一次。
# 需要注意的是这里的键值对应该有几种呢？  应该有三种花键
# 基本键值通过client类型[plus, basic]和idx[0,1,2,3,4,5,6,]来组装:
#  client_status_key  = f"status-{client_type}-{client_idx}", 其值为ClientStatus
#  client_status_start_time_key = f"{client_status_key}:start_time", 其值为时间戳, 记录当前状态的开始时间， 开始的时间。

    def get_client_status_key(self, client_type, client_idx):
        return f"status-{client_type}-{client_idx}"

    def get_client_status_start_time_key(self, client_type, client_idx):
        return f"{self.get_client_status_key(client_type, client_idx)}:start_time"

    def get_limited_message(self, start_time):
        current_time = time.time()
        print(f"current_time: {current_time}, start_time: {start_time}")
        time_passed = current_time - float(start_time)
        remaining_time = 8 * 3600 - time_passed
        remaining_time = int(remaining_time)
        return f"还需等待{remaining_time}秒恢复使用。"

    def set_client_limited(self, client_type, client_idx):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        # 设置键值对
        client_status_start_time_key = self.get_client_status_start_time_key(client_type, client_idx)
        self.redis.set(client_status_key, ClientStatus.CD.value)
        self.redis.set(client_status_start_time_key, time.time())

    def set_client_active(self, client_type, client_idx):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        self.redis.set(client_status_key, ClientStatus.ACTIVE.value)
        # client_status_start_time_key = self.get_client_status_start_time_key(client_type, client_idx


    def set_client_active_when_cd(self, client_type, client_idx):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        status = self.redis.get(client_status_key)
        if status == ClientStatus.CD.value:
            client_status_start_time_key = self.get_client_status_start_time_key(client_type, client_idx)
            current_time = time.time()
            passed_time = current_time - float(self.redis.get(client_status_start_time_key))
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
            self.redis.set(self.get_client_status_start_time_key(client_type, client_idx), time.time())



    def get_all_clients_status(self, basic_clients, plus_clients):
        clients_status = []
        for idx, client in enumerate(basic_clients):
            # 首先判断这两个key是否存在？ 如果不存在， 就设置。
            self.create_if_not_exist("basic", idx)

            is_active = self.set_client_active_when_cd("basic", idx)
            if is_active:
                _status = ClientStatus.ACTIVE.value
                _message = "可用"
            else:
                _status = ClientStatus.CD.value
                _message = self.get_limited_message(self.redis.get(self.get_client_status_start_time_key("basic", idx)))
            status = ClientsStatus(id=get_short_uuid(), status=_status, type="normal", idx=idx, message=_message)
            clients_status.append(status)
        for idx, client in enumerate(plus_clients):
            self.create_if_not_exist("plus", idx)
            is_active = self.set_client_active_when_cd("plus", idx)
            if is_active:
                _status = ClientStatus.ACTIVE.value
                _message = "可用"
            else:
                _status = ClientStatus.CD.value
                _message = self.get_limited_message(self.redis.get(self.get_client_status_start_time_key("basic", idx)))
            status = ClientsStatus(id=get_short_uuid(), status=_status, type="plus", idx=idx, message=_message)
            clients_status.append(status)

        return clients_status



