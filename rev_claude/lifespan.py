from contextlib import asynccontextmanager
from loguru import logger
from fastapi import FastAPI

from rev_claude.client.client_manager import ClientManager
from rev_claude.utils.time_zone_utils import set_cn_time_zone


async def on_startup():
    logger.info("Starting up")
    set_cn_time_zone()
    await ClientManager().load_clients()
    logger.info("Clients loaded")


def on_shutdown():
    logger.info("Shutting down")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    on_shutdown()
