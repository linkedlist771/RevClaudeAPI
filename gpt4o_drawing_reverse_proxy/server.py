import argparse
import fire
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import uvicorn
from loguru import logger
import time
import traceback
from typing import AsyncGenerator

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_URL = "https://gpt4oimagedrawing.585dg.com"

# Create JavaScript directory
js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')
os.makedirs(js_dir, exist_ok=True)


# Read JavaScript file function
def read_js_file(filename):
    file_path = os.path.join(js_dir, filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        # If file doesn't exist, create default content
        default_content = "// Default content for " + filename
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(default_content)
        return default_content


# Serve list.js file
@app.get('/list.js')
async def list_js():
    js_content = read_js_file('list.js')
    return Response(content=js_content, media_type='application/javascript')


# Generate modified content stream
async def generate_modified_stream(response) -> AsyncGenerator[bytes, None]:
    content_type = response.headers.get('Content-Type', '')

    # For non-HTML content, stream directly
    if 'text/html' not in content_type:
        async for chunk in response.aiter_bytes():
            yield chunk
        return

    # For HTML content, collect all chunks first
    content = b''
    async for chunk in response.aiter_bytes():
        content += chunk

    # Try to decode content
    try:
        html_content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            html_content = content.decode('latin-1')
        except Exception:
            # If all decoding attempts fail, return original content
            yield content
            return

    # Inject JavaScript
    if '</head>' in html_content:
        html_content = html_content.replace('</head>', '<script src="/list.js"></script></head>')
    elif '<body' in html_content:
        body_pos = html_content.find('<body')
        body_end = html_content.find('>', body_pos)
        if body_end != -1:
            html_content = (
                    html_content[:body_end + 1] +
                    '<script src="/list.js"></script>' +
                    html_content[body_end + 1:]
            )
    else:
        html_content = '<script src="/list.js"></script>' + html_content

    # Return modified content
    yield html_content.encode('utf-8')


# Main proxy route
@app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
async def proxy(request: Request, path: str = ""):
    start_time = time.time()
    logger.info(f"Proxying request to path: {path}")
    logger.info(f"Method: {request.method}")

    try:
        # Build target URL
        target_url = f"{TARGET_URL}/{path}"
        logger.info(f"Target URL: {target_url}")

        # Get request headers
        headers = {key: value for key, value in request.headers.items()
                   if key.lower() not in ['host', 'content-length']}
        headers['Host'] = TARGET_URL.split('//')[1]

        # Key change: Don't accept compressed content to correctly handle response
        headers['Accept-Encoding'] = 'identity'

        # Get request body
        body = await request.body()

        # Create a client to send request
        async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
            # Send request to target server
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body,
                cookies=request.cookies
            )

            # Handle redirects - similar to the Flask implementation
            if resp.status_code in [301, 302, 303, 307, 308]:
                logger.info(f"Redirect detected with status code: {resp.status_code}")

                # Get the location header
                location = resp.headers.get('Location', '')
                logger.info(f"Original redirect location: {location}")

                # Preserve all headers except content-length and transfer-encoding
                resp_headers = {k: v for k, v in resp.headers.items()
                                if k.lower() not in ['content-length', 'transfer-encoding']}

                # Return the redirect response as-is
                return Response(
                    content=b"",
                    status_code=resp.status_code,
                    headers=resp_headers
                )

            # Set up response headers, excluding problematic ones
            response_headers = {key: value for key, value in resp.headers.items()
                                if key.lower() not in ['content-length', 'transfer-encoding', 'content-encoding']}

            # Create a streaming response with modified content
            return StreamingResponse(
                generate_modified_stream(resp),
                status_code=resp.status_code,
                headers=response_headers
            )

    except httpx.TimeoutException:
        logger.error(f"Request timed out for {path}")
        return Response(
            content="The request to the target server timed out. Please try again later.".encode(),
            status_code=504
        )
    except httpx.ConnectError:
        logger.error(f"Connection error for {path}")
        return Response(
            content="Unable to connect to the target server. Please check your connection and try again.".encode(),
            status_code=502
        )
    except Exception as e:
        logger.error(f"Proxy error: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(
            content=f"Error: {str(e)}".encode(),
            status_code=500
        )
    finally:
        elapsed = time.time() - start_time
        logger.info(f"Request completed in {elapsed:.2f} seconds")


# Root path also uses proxy
@app.api_route('/', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
async def root_proxy(request: Request):
    return await proxy(request, "")


parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=5001, help="port")
parser.add_argument("--workers", default=1, type=int, help="workers")
args = parser.parse_args()


def start_server(port=args.port, host=args.host):
    logger.info(f"Starting server at {host}:{port}")
    logger.info(f"Proxy target URL: {TARGET_URL}")
    logger.info(f"JavaScript injection is enabled, will inject /list.js into all HTML responses")
    logger.info(f"JavaScript files directory: {js_dir}")

    # Configure logging
    logger.remove()  # Remove default handler
    logger.add(
        "proxy_server.log",
        rotation="10 MB",
        retention="1 week",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}"
    )
    # Also log to console
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}"
    )

    config = uvicorn.Config(app, host=host, port=port, workers=args.workers, log_level="info")
    server = uvicorn.Server(config=config)
    try:
        server.run()
    finally:
        logger.info("Server shutdown.")


if __name__ == '__main__':
    fire.Fire(start_server)