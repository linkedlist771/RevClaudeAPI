import json
from uuid import uuid4

import redis
from enum import Enum
import time
from pydantic import BaseModel
from loguru import logger
from rev_claude.configs import REDIS_HOST
from rev_claude.models import ClaudeModels


# from claude_cookie_manage import get_cookie_manager


class ClientStatus(Enum):
    ACTIVE = "active"
    ERROR = "error"
    BUSY = "busy"
    PART_CD = "part_cd"  # 部分账号cd
    CD = "cd"  # 等待刷新中。


class ClientsStatus(BaseModel):
    id: str
    status: str
    type: str
    idx: int
    message: str = ""
    is_session_login: bool = False
    meta_data: dict = {}


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

    def get_limited_message(self, start_time_key, type, idx):
        # 获取账号状态
        client_status_key = self.get_client_status_key(type, idx)
        status = self.redis.get(client_status_key)
        if status == ClientStatus.ERROR.value:
            return "账号异常"
        start_times = self.get_dict_value(start_time_key)

        message = ""
        current_time = time.time()

        for mode, start_time in start_times.items():

            # print(f"current_time: {current_time}, start_time: {start_time}")
            time_passed = current_time - float(start_time)
            remaining_time = 8 * 3600 - time_passed
            remaining_time = int(remaining_time)

            if remaining_time > 0:
                message += f"{mode}:还需等待{remaining_time}秒恢复使用。\n"
            else:
                message += f"{mode}:已经恢复使用。\n"
        return message

    def get_dict_value(self, key):
        value = self.redis.get(key)
        if value is None:
            return {}
        try:
            res = json.loads(value)
            if not isinstance(res, dict):
                return {}
            else:
                return res
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_client_limited(self, client_type, client_idx, start_time, model):

        # 都得传入模型进行设置，我看这样设计就比较好了
        client_status_key = self.get_client_status_key(client_type, client_idx)
        # 设置键值对
        client_status_start_time_key = self.get_client_status_start_time_key(
            client_type, client_idx
        )
        # if client_idx == 948928:
        #     logger.debug(f"status：{self.redis.get(client_status_key)}")
        # 首先判断这个是不是已经是cd状态了。
        if self.redis.get(client_status_key) == ClientStatus.CD.value:
            return

        self.redis.set(client_status_key, ClientStatus.CD.value)
        # 这里就设计到另一个设计了，
        # 首先获取这个字典对应的值
        start_time_dict = self.get_dict_value(client_status_start_time_key)
        # logger.debug(f"start_time_dict: {start_time_dict}")
        # logger.debug(f"model: {model}")
        # logger.debug(f"start_time: {start_time}")
        start_time_dict[model] = start_time
        self.redis.set(client_status_start_time_key, json.dumps(start_time_dict))

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
        # if client_idx == 948928:
        #     logger.debug(f"status: {status}")

        if status == ClientStatus.CD.value:
            client_status_start_time_key = self.get_client_status_start_time_key(
                client_type, client_idx
            )
            current_time = time.time()
            start_time_dict = self.get_dict_value(client_status_start_time_key)
            # if client_idx == 948928:
            #     logger.debug(f"start_time_dict: {start_time_dict}")
            for model, start_time in start_time_dict.items():
                time_elapsed = current_time - start_time
                if not (time_elapsed > 8 * 3600):
                    return False

            self.set_client_active(
                client_type, client_idx
            )  # 有一个可用就是可用， 否则其他的都是CD
            return True

            # passed_time = current_time - float(
            #     self.redis.get(client_status_start_time_key)
            # )
            # if passed_time > 8 * 3600:
            #     self.redis.set(client_status_key, ClientStatus.ACTIVE.value)
            #     return True
            # else:
            #     return False
        elif status == ClientStatus.ACTIVE.value:
            return True
        else:
            return False

    def create_if_not_exist(self, client_type: str, client_idx: int, models: list[str]):
        client_status_key = self.get_client_status_key(client_type, client_idx)
        start_time_key = self.get_client_status_start_time_key(client_type, client_idx)
        start_times = self.get_dict_value(start_time_key)
        # if client_idx == 948928:
        #     logger.debug(f"start_times: {start_times}")
        #     logger.debug(f"client_status_key: {client_status_key}")
        if (not self.redis.exists(client_status_key)) or (not start_times):
            self.redis.set(client_status_key, ClientStatus.ACTIVE.value)

            val = json.dumps({model: time.time() for model in models})
            self.redis.set(
                self.get_client_status_start_time_key(client_type, client_idx), val
            )

    async def get_all_clients_status(self, basic_clients, plus_clients):
        from rev_claude.cookie.claude_cookie_manage import CookieUsageType, get_cookie_manager

        async def retrieve_client_status(idx, client, client_type, models):
            self.create_if_not_exist(client_type, idx, models)
            account = await cookie_manager.get_account(client.cookie_key)
            is_active = self.set_client_active_when_cd(client_type, idx)

            if is_active:
                _status = ClientStatus.ACTIVE.value
                _message = "可用"
            else:
                _status = ClientStatus.CD.value
                key = self.get_client_status_start_time_key(client_type, idx)
                _message = self.get_limited_message(key, client_type, idx)
            client_type = "normal" if client_type == "basic" else client_type
            status = ClientsStatus(
                id=account,
                status=_status,
                type=client_type,
                idx=idx,
                message=_message,
            )
            return status

        async def process_clients(clients, client_type, models):
            """
            这个只处理是否为普通login的账号， 也就是说不为REVERSE_API_ONLY 就是OK的
            """
            for idx, client in clients.items():
                status = await retrieve_client_status(idx, client, client_type, models)
                cookie_key = client.cookie_key
                cookie_usage_type = await cookie_manager.get_cookie_usage_type(cookie_key)
                if cookie_usage_type != CookieUsageType.REVERSE_API_ONLY:
                    #
                    clients_status.append(status)

        async def add_session_login_account(clients, client_type, models):
            """
            同理， 这个只处理是否为session login的账号， 也就是说不为WEB_LOGIN_ONLY 就是OK的
            """
            for idx, client in clients.items():
                status = await retrieve_client_status(idx, client, client_type, models)
                status.is_session_login = True
                cookie_key = client.cookie_key
                cookie_usage_type = await cookie_manager.get_cookie_usage_type(cookie_key)
                if cookie_usage_type != CookieUsageType.WEB_LOGIN_ONLY:
                    clients_status.append(status)

        clients_status = []
        cookie_manager = get_cookie_manager()
        if plus_clients:
            # 当然是全部都要测试了， 但是这个for循环了两次， 感觉不太好， anyway。
            last_plus_idx = list(plus_clients.keys())
            if not isinstance(last_plus_idx, list):
                last_plus_idx = [last_plus_idx]
            await add_session_login_account(
                {
                    __last_plus_idx: plus_clients[__last_plus_idx]
                    for __last_plus_idx in last_plus_idx
                },
                "plus",
                [ClaudeModels.OPUS.value, ClaudeModels.SONNET_3_5.value],
            )

        await process_clients(
            plus_clients,
            "plus",
            [ClaudeModels.OPUS.value, ClaudeModels.SONNET_3_5.value],
        )

        if basic_clients:
            # 当然是全部都要测试了， 但是这个for循环了两次， 感觉不太好， anyway。
            first_basic_idx = list(basic_clients.keys())
            await add_session_login_account(
                # {first_basic_idx: basic_clients[first_basic_idx]},
                {basic_idx: basic_clients[basic_idx] for basic_idx in first_basic_idx},
                "basic",
                [ClaudeModels.SONNET_3_5.value],
            )

        await process_clients(basic_clients, "basic", [ClaudeModels.SONNET_3_5.value])
        # TODO: 添加获取用于处理session登录所使用的账号。
        # 现在就取plus的最后一共和basic的第一个
        # 添加获取用于处理session登录所使用的账号
        # 取plus的最后一个和basic的第一个
        # 分别添加 plus 和 basic 客户端的 session 登录账号

        return clients_status
