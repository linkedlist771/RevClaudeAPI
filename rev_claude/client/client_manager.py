from rev_claude.cookie.claude_cookie_manage import get_cookie_manager


class ClientManager:
    basic_clients: list = []
    plus_clients: list = []


    def load_clients(self):
        cookie_manager = get_cookie_manager()
        basic_clients, plus_clients = cookie_manager.get_all_basic_and_plus_client()
        ClientManager.basic_clients = basic_clients
        ClientManager.plus_clients = plus_clients

    def get_clients(self):
        return ClientManager.basic_clients, ClientManager.plus_clients