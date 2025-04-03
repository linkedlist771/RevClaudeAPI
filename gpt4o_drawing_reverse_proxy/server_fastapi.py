import argparse
import asyncio
import os
import time
import fire
import aiohttp
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from utils import read_js_file
from configs import IMAGES_DIR, JS_DIR, ROOT, SERVER_BASE_URL, TARGET_URL

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


# Process response content function
async def process_response(response):
    content_type = response.headers.get("Content-Type", "")
    # For non-HTML content, return directly
    if "text/html" not in content_type:
        return await response.read()

    # Process HTML content
    content = await response.read()

    # Try to decode content
    try:
        html_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            html_content = content.decode("latin-1")
        except Exception:
            return content
    # Inject JavaScript
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

    return html_content.encode("utf-8")


# Create a stream generator for aiohttp responses
async def stream_response_content(response):
    chunk_size = 1024
    async for chunk in response.content.iter_chunked(chunk_size):
        yield chunk


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
    response = None
    # Create aiohttp ClientSession
    session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=60, connect=30, sock_read=30, sock_connect=30),
        cookie_jar=aiohttp.CookieJar()
    )

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

    # Get cookies from request
    cookies = request.cookies
    logger.debug(f"cookies:\n{cookies}")

    try:
        # Make the request with aiohttp
        response = await session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.query_params,
            data=body,
            cookies=cookies,
            allow_redirects=False,  # Don't automatically follow redirects
        )

        # Handle redirect responses
        if response.status in [301, 302, 303, 307, 308]:
            location = response.headers.get("Location", "")
            response_headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() not in ["content-length", "transfer-encoding"]
            }
            response_headers["Location"] = location
            content = await response.read()
            # await response.release()
            # await session.close()
            return Response(
                content=content,
                status_code=response.status,
                headers=response_headers,
            )

        # Check content type
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            # Process response headers
            response_headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() not in ["content-length", "transfer-encoding"]
            }

            # Return streaming response
            # Note: We need to close the session after the streaming is complete
            # This is handled in the generator and this requires separate handling
            streaming_response = StreamingResponse(
                stream_response_content(response),
                status_code=response.status,
                headers=response_headers,
            )

            # Important: We need to manage the session lifecycle - this is a key difference from httpx
            # We need to ensure cleanup when the stream is done
            # async def cleanup():
            #     # Wait for streaming to complete before closing
            #     await asyncio.sleep(0.1)  # Give time for streaming to start
            #     await response.release()
            #     await session.close()
            #
            # # Start cleanup task - this runs in the background
            # asyncio.create_task(cleanup())

            return streaming_response
        else:
            # For HTML content, use the existing processing method
            content = await process_response(response)
            if "Content failed to load" in str(content):
                logger.debug(f"content:\n{content}")

            response_headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower()
                   not in ["content-length", "transfer-encoding", "content-encoding"]
            }

            # Preserve any cookies from the response
            # aiohttp handles cookies differently than httpx
            cookies_to_set = []
            for key, morsel in session.cookie_jar.filter_cookies(response.url).items():
                cookie_header = f"{key}={morsel.value}; Path=/"
                cookies_to_set.append(cookie_header)

            if cookies_to_set:
                response_headers["set-cookie"] = cookies_to_set

            # # Clean up resources
            # await response.release()
            # await session.close()

            return Response(
                content=content,
                status_code=response.status,
                headers=response_headers,
            )
    except asyncio.TimeoutError:
        logger.error(f"Request timed out for {target_url}")
        # await session.close()
        return Response(
            content="The request to the target server timed out. Please try again later.".encode(),
            status_code=504,
        )
    except aiohttp.ClientConnectorError:
        logger.error(f"Connection error for {target_url}")
        # await session.close()
        return Response(
            content="Unable to connect to the target server. Please check your connection and try again.".encode(),
            status_code=502,
        )
    except Exception as e:
        logger.error(f"Proxy error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # await session.close()
        return Response(content=f"Error: {str(e)}".encode(), status_code=500)
    finally:
        elapsed = time.time() - start_time
        logger.info(f"Request completed in {elapsed:.2f} seconds")
        if response:
            # Close the response and session
            await response.release()
        await session.close()


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