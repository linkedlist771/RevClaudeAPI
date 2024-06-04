from rev_claude.cookie.claude_cookie_manage import get_cookie_manager
from loguru import logger
HASH_MODULE = 1e6


def custom_hash(key: str):
    # 获取每个char的ascii码，然后相加
    return sum([ord(c) for c in key])

class ClientManager:
    basic_clients: dict = {}
    plus_clients: dict = {}

    def load_clients(self):
        cookie_manager = get_cookie_manager()
        basic_clients, plus_clients = cookie_manager.get_all_basic_and_plus_client()
        ClientManager.basic_clients = {
            int(custom_hash(client.cookie_key) % HASH_MODULE): client for client in basic_clients
        }
        ClientManager.plus_clients = {
            int(custom_hash(client.cookie_key) % HASH_MODULE): client for client in plus_clients
        }
        logger.info(f"basic_clients: {ClientManager.basic_clients.keys()}")
        logger.info(f"plus_clients: {ClientManager.plus_clients.keys()}")

    def get_clients(self):
        return ClientManager.basic_clients, ClientManager.plus_clients
