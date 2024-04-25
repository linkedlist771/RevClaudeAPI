# Standard Library Imports
import argparse
import configparser
import json
import os
import sys
import time
import utility
import urllib.parse
import itertools

# Third-Party Imports
import fire
import uvicorn
from fastapi import FastAPI, HTTPException, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from h11 import Response
from pydantic import BaseModel
from anyio import Path
from loguru import logger
import claude
from router import router
from claude_cookie_manage import get_cookie_manager
from utility import get_client_status

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=6238, help="port")
parser.add_argument("--pattern", default="dev", help="pattern")
args = parser.parse_args()


#############################################
####                                     ####
#####          Global Initilize         #####
####                                     ####

"""Config file name and paths for chatbot API configuration."""
CONFIG_FILE_NAME = "Config.conf"
CLAUDE_COOKIE_JSON = "claude_config.json"
CONFIG_FOLDER = os.getcwd()


"""Disable search on files cookie(fix 'PermissionError: [Errno 1] Operation not permitted') now used only for Claude"""
ISCONFIGONLY = False

# CONFIG_FOLDER = os.path.expanduser("~/.config")
# CONFIG_FOLDER = Path(CONFIG_FOLDER) / "WebAI_to_API"

# init logger
logger.add("log_file.log", rotation="1 week")  # 每周轮换一次文件



FixConfigPath = lambda: (
    Path(CONFIG_FOLDER) / CONFIG_FILE_NAME
    if os.path.basename(CONFIG_FOLDER).lower() == "src"
    else Path(CONFIG_FOLDER) / "src" / CONFIG_FILE_NAME
)

"""Path to API configuration file."""
CONFIG_FILE_PATH = FixConfigPath()


def ResponseModel():
    config = configparser.ConfigParser()
    config.read(filenames=CONFIG_FILE_PATH)
    return config.get("Main", "Model", fallback="Claude")


OpenAIResponseModel = ResponseModel()

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


# if args.pattern == "dev":
#     COOKIE_CLAUDE = None
#     CLAUDE_CLIENT = None
# else:
#     COOKIE_CLAUDE = utility.getClaudeCookieFromJson(
#         CLAUDE_COOKIE_JSON
#     )  # message.session_id
#     CLAUDE_CLIENT = claude.Client(COOKIE_CLAUDE)
cookie_manager = get_cookie_manager()
basic_clients, plus_clients = cookie_manager.get_all_basic_and_plus_client()
# client_round_robin = ClientRoundRobin(basic_clients, plus_clients)


"""FastAPI application instance."""

app = FastAPI()

# Add CORS middleware to allow all origins, credentials, methods, and headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# add index route
app.mount("/static", StaticFiles(directory="frontui"), name="static")


@app.get("/")
async def index():
    # use the index.html file in the frontui/ folder
    return FileResponse("frontui/index.html")


@app.get("/api/v1/clients_status")
async def _get_client_status():
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
