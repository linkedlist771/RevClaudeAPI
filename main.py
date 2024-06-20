import argparse
import fire
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from rev_claude.client.client_manager import ClientManager
from rev_claude.lifespan import lifespan
from rev_claude.middlewares.register_middlewares import register_middleware
from rev_claude.router import router
from utility import get_client_status

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=6238, help="port")
args = parser.parse_args()
logger.add("log_file.log", rotation="1 week")  # 每周轮换一次文件
app = FastAPI(lifespan=lifespan)


app = register_middleware(app)


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
