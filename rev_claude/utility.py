from typing import List
from rev_claude.status.clients_status_manager import ClientsStatus, ClientsStatusManager
from time import time


def get_current_time() -> int:
    return int(time())


def get_client_status(basic_clients, plus_clients) -> List[ClientsStatus]:
    clients_status_manager = ClientsStatusManager()
    return clients_status_manager.get_all_clients_status(basic_clients, plus_clients)
