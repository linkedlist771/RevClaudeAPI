import argparse

import fire
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import uvicorn
from starlette.background import BackgroundTask
from loguru import logger
import time

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


# Process response content function
async def process_response(response):
    content_type = response.headers.get('Content-Type', '')

    # For non-HTML content, return directly
    if 'text/html' not in content_type:
        return response.read()

    # Process HTML content
    content = response.read()

    # Try to decode content
    try:
        html_content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            html_content = content.decode('latin-1')
        except Exception:
            return content
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

    return html_content.encode('utf-8')


# Main proxy route
@app.api_route('/', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
async def proxy(request: Request, path: str = ""):
    if "error" in str(path):
        # 204 not found
        return Response(
            status_code=204,
            content="",
            media_type="application/json"
        )

    start_time = time.time()
    logger.debug(f"Proxying request to path: {path}")
    logger.debug(f"Method: {request.method}")
    logger.debug(f"Client IP: {request.client.host if request.client else 'unknown'}")

    # Create a client with appropriate timeout settings
    async with httpx.AsyncClient(
            follow_redirects=False,  # CRITICAL CHANGE: Don't automatically follow redirects
            timeout=30.0  # Increase timeout to 30 seconds
    ) as client:
        target_url = f"{TARGET_URL}/{path}"
        logger.info(f"Target URL: {target_url}")

        # Get request headers
        headers = {key: value for key, value in request.headers.items()
                   if key.lower() not in ['host', 'content-length']}
        headers['Host'] = TARGET_URL.split('//')[1]
        headers['Accept-Encoding'] = 'identity'

        # Get request body
        body = await request.body()

        # Get cookies from request
        cookies = request.cookies

        try:
            if "backend-api/conversation" in str(path) and request.method == "POST":
                async with client.stream(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        params=request.query_params,
                        content=body,
                        cookies=cookies,
                        follow_redirects=False
                ) as response:
                    # Create a buffer to store chunks while the response is open
                    chunks = []
                    async for chunk in response.aiter_bytes():
                        if chunk:  # Only store non-empty chunks
                            logger.debug(chunk)
                            chunks.append(chunk)

                    # Create a function that yields from the stored chunks
                    async def stream_from_buffer():
                        for chunk in chunks:
                            yield chunk

                    # Return a streaming response from our buffer
                    return StreamingResponse(
                        stream_from_buffer(),
                        status_code=response.status_code,
                        headers=response.headers
                    )
            else:
                # Send request to target server
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    params=request.query_params,
                    content=body,
                    cookies=cookies,  # Pass cookies directly
                    follow_redirects=False  # CRITICAL CHANGE: Don't automatically follow redirects
                )

            # Handle redirect responses
            if response.status_code in [301, 302, 303, 307, 308]:
                location = response.headers.get('Location', '')
                logger.debug(f"Redirect detected to: {location}")
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding']}
                response_headers['Location'] = location
                cookies = response.cookies
                content = response.content
                # Add debugging
                logger.debug(f"Returning redirect to: {location}")
                logger.debug(f"Status code: {response.status_code}")
                logger.debug(f"Headers: {response_headers}")
                # Create response with the proper redirect status and location
                return Response(
                    content=content,
                    status_code=response.status_code,
                    headers=response_headers
                )
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            logger.debug(f"content_type:{content_type}")
            # For streaming responses, use StreamingResponse
            if ('text/event-stream' in content_type):
                # Process response headers
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding']}

                # Return streaming response
                return StreamingResponse(
                    response.aiter_bytes(),
                    status_code=response.status_code,
                    headers=response_headers
                )
            else:
                # For HTML content, use the existing processing method
                content = await process_response(response)
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding', 'content-encoding']}

                # Preserve any cookies from the response
                for cookie_name, cookie_value in response.cookies.items():
                    cookie_header = f"{cookie_name}={cookie_value}; Path=/"
                    if 'set-cookie' in response_headers:
                        if not isinstance(response_headers['set-cookie'], list):
                            response_headers['set-cookie'] = [response_headers['set-cookie']]
                        response_headers['set-cookie'].append(cookie_header)
                    else:
                        response_headers['set-cookie'] = cookie_header

                return Response(
                    content=content,
                    status_code=response.status_code,
                    headers=response_headers
                )
        except httpx.TimeoutException:
            logger.error(f"Request timed out for {target_url}")
            return Response(
                content="The request to the target server timed out. Please try again later.".encode(),
                status_code=504
            )
        except httpx.ConnectError:
            logger.error(f"Connection error for {target_url}")
            return Response(
                content="Unable to connect to the target server. Please check your connection and try again.".encode(),
                status_code=502
            )
        except Exception as e:
            logger.error(f"Proxy error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                content=f"Error: {str(e)}".encode(),
                status_code=500
            )
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

    config = uvicorn.Config(app, host=host, port=port, workers=args.workers, log_level="info")
    server = uvicorn.Server(config=config)
    try:
        server.run()
    finally:
        logger.info("Server shutdown.")


if __name__ == '__main__':
    fire.Fire(start_server)