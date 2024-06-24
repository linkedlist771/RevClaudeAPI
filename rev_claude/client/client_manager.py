from rev_claude.cookie.claude_cookie_manage import get_cookie_manager
from loguru import logger
import hashlib

HASH_MODULE = 1e6


def improved_hash(key: str, seed: str = "your_secret_seed"):
    h = hashlib.sha256()
    h.update((key + seed).encode())  # Combine key and seed
    return int(h.hexdigest(), 16) % HASH_MODULE


class ClientManager:
    basic_clients: dict = {}
    plus_clients: dict = {}

    async def load_clients(self, reload: bool = False):
        cookie_manager = get_cookie_manager()
        basic_clients, plus_clients = (
            await cookie_manager.get_all_basic_and_plus_client(reload)
        )
        ClientManager.basic_clients = {
            int(improved_hash(client.cookie_key)): client for client in basic_clients
        }
        ClientManager.plus_clients = {
            int(improved_hash(client.cookie_key)): client for client in plus_clients
        }
        logger.info(f"basic_clients: {ClientManager.basic_clients.keys()}")
        logger.info(f"plus_clients: {ClientManager.plus_clients.keys()}")

    def get_clients(self):
        return ClientManager.basic_clients, ClientManager.plus_clients
