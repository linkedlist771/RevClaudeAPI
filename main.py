# Standard Library Imports
import argparse
import itertools

# Third-Party Imports
import fire
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from rev_claude.client.client_manager import ClientManager
from rev_claude.lifespan import lifespan
from rev_claude.router import router
from rev_claude.cookie.claude_cookie_manage import get_cookie_manager
from utility import get_client_status

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=6238, help="port")
parser.add_argument("--pattern", default="dev", help="pattern")
args = parser.parse_args()
# init logger
logger.add("log_file.log", rotation="1 week")  # 每周轮换一次文件


""" Initialization AI Models and Cookies """


class ClientRoundRobin:
    def __init__(self, basic_clients, plus_clients):
        self.basic_clients = basic_clients
        self.basic_cycle = itertools.cycle(self.basic_clients)
        self.plus_clients = plus_clients
        self.plus_cycle = itertools.cycle(self.plus_clients)

    def get_next_basic_client(self):
        return next(self.basic_cycle)

    def get_next_plus_client(self):
        return next(self.plus_cycle)



"""FastAPI application instance."""

app = FastAPI(lifespan=lifespan)

# cookie_manager = get_cookie_manager()
# basic_clients, plus_clients = cookie_manager.get_all_basic_and_plus_client()



# Add CORS middleware to allow all origins, credentials, methods, and headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# add index route
# app.mount("/static", StaticFiles(directory="frontui"), name="static")

@app.get("/api/v1/clients_status")
async def _get_client_status():
    basic_clients, plus_clients = ClientManager().get_clients()
    return get_client_status(basic_clients, plus_clients)


def start_server(port=args.port, host=args.host):
    logger.info(f"Starting server at {host}:{port}")
    app.include_router(router)
    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config=config)
    try:
        server.run()
    finally:
        logger.info("Server shutdown.")


if __name__ == "__main__":
    fire.Fire(start_server)
