import argparse

import fire
import uvicorn
from configs import TARGET_URL
from fastapi.middleware.cors import CORSMiddleware
from fastapi_proxy_lib.fastapi.app import reverse_http_app
from loguru import logger

parser = argparse.ArgumentParser()
parser.add_argument("--base_url", required=True, help="Base URL for the proxy")
parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=5001, help="port")
parser.add_argument("--workers", default=4, type=int, help="workers")
args = parser.parse_args()

# app = reverse_http_app(base_url="https://poe.com/")
app = reverse_http_app(base_url=args.base_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def start_server(port=args.port, host=args.host):
    logger.info(f"Starting server at {host}:{port}")
    logger.info(f"Proxy target URL: {TARGET_URL}")

    # Configure more detailed logging

    config = uvicorn.Config(
        app, host=host, port=port, workers=args.workers, log_level="info"
    )
    server = uvicorn.Server(config=config)
    try:
        server.run()
    finally:
        logger.info("Server shutdown.")


if __name__ == "__main__":
    fire.Fire(start_server)
