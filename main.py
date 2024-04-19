# Standard Library Imports
import argparse
import configparser
import json
import os
import sys
import time
import utility
import urllib.parse
# Third-Party Imports
import fire
import uvicorn
from fastapi import FastAPI, HTTPException, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from h11 import Response
from pydantic import BaseModel
from anyio import Path
from loguru import logger
import claude
from router import  router



parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=6238, help="port")
args = parser.parse_args()


#############################################
####                                     ####
#####          Global Initilize         #####
####                                     ####

"""Config file name and paths for chatbot API configuration."""
CONFIG_FILE_NAME = "Config.conf"
CONFIG_FOLDER = os.getcwd()

"""Disable search on files cookie(fix 'PermissionError: [Errno 1] Operation not permitted') now used only for Claude"""
ISCONFIGONLY = False

# CONFIG_FOLDER = os.path.expanduser("~/.config")
# CONFIG_FOLDER = Path(CONFIG_FOLDER) / "WebAI_to_API"



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
COOKIE_CLAUDE = None# utility.getCookie_Claude(configfilepath=CONFIG_FILE_PATH, configfilename=CONFIG_FILE_NAME) #message.session_id
CLAUDE_CLIENT = None # claude.Client(COOKIE_CLAUDE)

"""FastAPI application instance."""

app = FastAPI()

# Add CORS middleware to allow all origins, credentials, methods, and headers.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )





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