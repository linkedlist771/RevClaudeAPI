import argparse

import fire
import uvicorn
from fastapi import FastAPI
from fastapi_proxy_lib.fastapi.router import RouterHelper

from configs import TARGET_URL
from fastapi.middleware.cors import CORSMiddleware
from fastapi_proxy_lib.core.http import ForwardHttpProxy, ReverseHttpProxy

from fastapi_proxy_lib.fastapi.app import reverse_http_app, reverse_ws_app
from fastapi_proxy_lib.core.http import ForwardHttpProxy, ReverseHttpProxy
from fastapi_proxy_lib.core.websocket import (
    DEFAULT_KEEPALIVE_PING_INTERVAL_SECONDS,
    DEFAULT_KEEPALIVE_PING_TIMEOUT_SECONDS,
    DEFAULT_MAX_MESSAGE_SIZE_BYTES,
    DEFAULT_QUEUE_SIZE,
    ReverseWebSocketProxy,
)

from loguru import logger

parser = argparse.ArgumentParser()
parser.add_argument(
    "--http_base_url", required=True, help="Base http URL for the proxy"
)
parser.add_argument("--ws_base_url", required=True, help="Base ws URL for the proxy")

parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=5001, help="port")
parser.add_argument("--workers", default=4, type=int, help="workers")
args = parser.parse_args()


def reverse_http_and_ws_app(http_base_url: str, ws_base_url: str):
    reverse_http_proxy = ReverseHttpProxy(
        None,
        base_url=http_base_url,
        follow_redirects=False,
    )
    reverse_websocket_proxy = ReverseWebSocketProxy(
        None,
        base_url=ws_base_url,
        follow_redirects=False,
        max_message_size_bytes=DEFAULT_MAX_MESSAGE_SIZE_BYTES,
        queue_size=DEFAULT_QUEUE_SIZE,
        keepalive_ping_interval_seconds=DEFAULT_KEEPALIVE_PING_INTERVAL_SECONDS,
        keepalive_ping_timeout_seconds=DEFAULT_KEEPALIVE_PING_TIMEOUT_SECONDS,
    )
    """Util function to register proxy to FastAPI app."""
    # 注意必须要新实例化一个 RouterHelper ,否则共享 RouterHelper 会导致其他app的客户端被关闭
    helper = RouterHelper()
    router = helper.register_router(reverse_http_proxy)
    router = helper.register_router(reverse_websocket_proxy, router)
    app = FastAPI(lifespan=helper.get_lifespan())
    app.include_router(router)

    return app


# app = reverse_http_app(base_url="https://poe.com/")
app = reverse_http_and_ws_app(
    http_base_url=args.http_base_url, ws_base_url=args.ws_base_url
)

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
