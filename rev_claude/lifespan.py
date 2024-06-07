from contextlib import asynccontextmanager
from loguru import logger
from fastapi import FastAPI

from rev_claude.client.client_manager import ClientManager


async def on_startup():
    logger.info("Starting up")
    await ClientManager().load_clients()
    logger.info("Clients loaded")


def on_shutdown():
    logger.info("Shutting down")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    on_shutdown()
