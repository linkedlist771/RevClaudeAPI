from rev_claude.cookie.claude_cookie_manage import get_cookie_manager

HASH_MODULE = 1e6

class ClientManager:
    basic_clients:  dict = {}
    plus_clients: dict = {}



    def load_clients(self):
        cookie_manager = get_cookie_manager()
        basic_clients, plus_clients = cookie_manager.get_all_basic_and_plus_client()
        ClientManager.basic_clients = {
            hash(client.cookie_key) % HASH_MODULE: client for client in basic_clients
        }
        ClientManager.plus_clients = {
            hash(client.cookie_key) % HASH_MODULE: client for client in plus_clients
        }

    def get_clients(self):
        return ClientManager.basic_clients, ClientManager.plus_clients