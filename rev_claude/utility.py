from time import time
from typing import List

from rev_claude.status.clients_status_manager import (ClientsStatus,
                                                      ClientsStatusManager)


def get_current_time() -> int:
    return int(time())


async def get_client_status(basic_clients, plus_clients) -> List[ClientsStatus]:
    clients_status_manager = ClientsStatusManager()
    return await clients_status_manager.get_all_clients_status(
        basic_clients, plus_clients
    )
