import argparse
import asyncio
import time

import fire
import httpx
import uvicorn
from configs import TARGET_URL
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from utils import read_js_file

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Serve list.js file
@app.get("/list.js")
async def list_js():
    js_content = read_js_file("list.js")
    return Response(content=js_content, media_type="application/javascript")


# Main proxy route
@app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def proxy(request: Request, path: str = ""):
    if "error" in str(path):
        # 204 not found
        return Response(status_code=204, content="", media_type="application/json")

    start_time = time.time()
    target_url = f"{TARGET_URL}/{path}"

    # Get request headers
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ["host", "content-length"]
    }
    headers["Host"] = TARGET_URL.split("//")[1]
    headers["Accept-Encoding"] = "identity"

    # Get request body
    body = await request.body()
    cookies = request.cookies

    try:
        async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=httpx.Timeout(60.0, connect=30.0, read=30.0, write=30.0, pool=30.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        ) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body,
                cookies=cookies,
                follow_redirects=False,
            )

            # Handle redirect responses
            if response.status_code in [301, 302, 303, 307, 308]:
                location = response.headers.get("Location", "")
                response_headers = {key: value for key, value in response.headers.items()}
                response_headers["Location"] = location
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response_headers,
                )

            # Check content type
            content_type = response.headers.get("Content-Type", "")

            # 处理非HTML内容
            if "text/html" not in content_type:
                return StreamingResponse(
                    response.aiter_bytes(),
                    status_code=response.status_code,
                    headers=response.headers,
                    media_type=content_type
                )

            # 处理HTML内容
            async def process_html():
                full_content = await response.aread()

                try:
                    html_content = full_content.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        html_content = full_content.decode("latin-1")
                    except Exception:
                        yield full_content
                        return

                # 注入JavaScript
                if "</head>" in html_content:
                    html_content = html_content.replace(
                        "</head>", '<script src="/list.js"></script></head>'
                    )
                elif "<body" in html_content:
                    body_pos = html_content.find("<body")
                    body_end = html_content.find(">", body_pos)
                    if body_end != -1:
                        html_content = (
                                html_content[: body_end + 1]
                                + '<script src="/list.js"></script>'
                                + html_content[body_end + 1:]
                        )
                else:
                    html_content = '<script src="/list.js"></script>' + html_content

                yield html_content.encode("utf-8")

            response_headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() not in ["content-length", "transfer-encoding", "content-encoding"]
            }

            return StreamingResponse(
                process_html(),
                status_code=response.status_code,
                headers=response_headers,
                media_type=content_type
            )

    except httpx.TimeoutException:
        logger.error(f"Request timed out for {target_url}")
        return Response(
            content="The request to the target server timed out. Please try again later.".encode(),
            status_code=504,
        )
    except httpx.ConnectError:
        logger.error(f"Connection error for {target_url}")
        return Response(
            content="Unable to connect to the target server. Please check your connection and try again.".encode(),
            status_code=502,
        )
    except Exception as e:
        logger.error(f"Proxy error: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return Response(content=f"Error: {str(e)}".encode(), status_code=500)
    finally:
        elapsed = time.time() - start_time
        logger.info(f"Request completed in {elapsed:.2f} seconds")


parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=5001, help="port")
parser.add_argument("--workers", default=1, type=int, help="workers")
args = parser.parse_args()


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