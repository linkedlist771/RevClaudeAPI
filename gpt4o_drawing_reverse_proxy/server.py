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
import re
from urllib.parse import urljoin, urlparse

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
async def generate_modified_stream(response, request) -> AsyncGenerator[bytes, None]:
    content_type = response.headers.get('Content-Type', '')

    # Handle CSS content specifically
    if 'text/css' in content_type:
        logger.info(f"Processing CSS content: {content_type}")
        content = b''
        async for chunk in response.aiter_bytes():
            content += chunk

        # CSS content should not be empty
        if not content:
            logger.error("CSS content is empty, this is likely an error")
            yield b"/* Error: CSS content was empty */"
            return

        # Try to decode and rewrite URLs in CSS
        try:
            css_content = content.decode('utf-8')
            host = request.headers.get('Host', '')
            scheme = request.headers.get('X-Forwarded-Proto', 'http')  # Get original scheme

            # Rewrite absolute URLs in CSS
            css_content = re.sub(r'url\((["\']?)' + re.escape(TARGET_URL) + '/', f'url(\\1{scheme}://{host}/',
                                 css_content)

            # Rewrite relative URLs in CSS
            css_content = re.sub(r'url\((["\']?)/', f'url(\\1{scheme}://{host}/', css_content)

            yield css_content.encode('utf-8')
        except Exception as e:
            logger.error(f"Error processing CSS: {str(e)}")
            # If anything fails, return original content
            yield content
        return

    # For other non-HTML content, stream directly
    if 'text/html' not in content_type:
        # Don't modify, just stream
        content = b''
        async for chunk in response.aiter_bytes():
            content += chunk
        if not content and 'javascript' in content_type:
            logger.warning(f"Empty JS content detected for content-type: {content_type}")
        yield content
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

    # Get our server's host for URL rewriting
    host = request.headers.get('Host', '')

    # Get the scheme (http or https)
    scheme = request.headers.get('X-Forwarded-Proto', 'http')

    # Fix absolute URLs to resources
    html_content = html_content.replace(f'href="{TARGET_URL}/', f'href="{scheme}://{host}/')
    html_content = html_content.replace(f'src="{TARGET_URL}/', f'src="{scheme}://{host}/')

    # Fix URLs with single quotes
    html_content = html_content.replace(f"href='{TARGET_URL}/", f"href='{scheme}://{host}/")
    html_content = html_content.replace(f"src='{TARGET_URL}/", f"src='{scheme}://{host}/")

    # Fix relative URLs
    html_content = html_content.replace('href="/', f'href="{scheme}://{host}/')
    html_content = html_content.replace('src="/', f'src="{scheme}://{host}/')
    html_content = html_content.replace("href='/", f"href='{scheme}://{host}/")
    html_content = html_content.replace("src='/", f"src='{scheme}://{host}/")

    # Fix relative URLs without leading slash
    html_content = re.sub(r'(href=["\']\s*)(?!(http|https|data|javascript|#|\/))([^"\']+["\']\s*)',
                          f'\\1{scheme}://{host}/\\3', html_content)
    html_content = re.sub(r'(src=["\']\s*)(?!(http|https|data|javascript|#|\/))([^"\']+["\']\s*)',
                          f'\\1{scheme}://{host}/\\3', html_content)

    # Fix CSS URLs in style tags
    html_content = re.sub(r'url\((["\']?)/', f'url(\\1{scheme}://{host}/', html_content)
    html_content = re.sub(r'url\((["\']?)' + re.escape(TARGET_URL) + '/', f'url(\\1{scheme}://{host}/', html_content)
    html_content = re.sub(r'url\((["\']?)(?!(http|https|data|#))([^"\')\s]+)(["\']?)\)',
                          f'url(\\1{scheme}://{host}/\\3\\4)', html_content)

    # Fix action attributes in forms
    html_content = html_content.replace('action="/', f'action="{scheme}://{host}/')
    html_content = html_content.replace(f'action="{TARGET_URL}/', f'action="{scheme}://{host}/')
    html_content = re.sub(r'(action=["\']\s*)(?!(http|https|data|javascript|#|\/))([^"\']+["\']\s*)',
                          f'\\1{scheme}://{host}/\\3', html_content)

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
@app.api_route('/', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
async def proxy(request: Request, path: str = ""):
    start_time = time.time()
    logger.info(f"Proxying request to path: {path}")
    logger.info(f"Method: {request.method}")

    # Log important headers to help debug
    logger.info(f"Host: {request.headers.get('Host')}")
    logger.info(f"User-Agent: {request.headers.get('User-Agent')}")
    logger.info(f"Content-Type: {request.headers.get('Content-Type')}")
    logger.info(f"Accept: {request.headers.get('Accept')}")

    # Handle the protocol (HTTP/HTTPS)
    scheme = request.headers.get('X-Forwarded-Proto', 'http')
    logger.info(f"Scheme: {scheme}")

    try:
        # Handle paths that don't start with slash (relative paths)
        if path and path.startswith('/'):
            target_url = f"{TARGET_URL}{path}"
        else:
            # For paths like "ulp/react-components/1.86.8/css/main.cdn.min.css"
            target_url = f"{TARGET_URL}/{path}"

        # Log the URL we're about to request
        logger.info(f"Target URL: {target_url}")

        # Check if it's a CSS request
        if path.endswith('.css'):
            logger.info(f"CSS file detected: {path}")

        # Get request headers
        headers = {key: value for key, value in request.headers.items()
                   if key.lower() not in ['host', 'content-length']}
        headers['Host'] = TARGET_URL.split('//')[1]

        # Key change: Don't accept compressed content to correctly handle response
        headers['Accept-Encoding'] = 'identity'

        # Get request body
        body = await request.body()

        # Create a client to send request with proper timeout
        async with httpx.AsyncClient(follow_redirects=False, timeout=60.0) as client:
            # Send request to target server
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body,
                cookies=request.cookies
            )

            # Handle redirects - improved implementation
            if resp.status_code in [301, 302, 303, 307, 308]:
                logger.info(f"Redirect detected with status code: {resp.status_code}")

                # Get the location header
                location = resp.headers.get('Location', '')
                logger.info(f"Original redirect location: {location}")

                # Get the scheme for the redirect
                scheme = request.headers.get('X-Forwarded-Proto', 'http')

                # Modify the location header to point back to our proxy
                if location.startswith(TARGET_URL):
                    # Replace target URL with our proxy URL
                    new_location = location.replace(TARGET_URL, f"{scheme}://{request.headers.get('Host', '')}")
                elif location.startswith('http'):
                    # For other absolute URLs, keep them as is
                    new_location = location
                elif location.startswith('/'):
                    # For relative URLs, prepend our server's host
                    new_location = f"{scheme}://{request.headers.get('Host', '')}{location}"
                else:
                    # For other URLs (like relative without leading slash)
                    # Use urllib.parse to properly handle relative URLs
                    base_url = f"{scheme}://{request.headers.get('Host', '')}/{path}"
                    new_location = urljoin(base_url, location)
                    logger.info(f"Relative redirect: Base URL={base_url}, Location={location}, Result={new_location}")

                logger.info(f"Modified redirect location: {new_location}")

                # Preserve all headers except content-length and transfer-encoding
                resp_headers = {k: v for k, v in resp.headers.items()
                                if k.lower() not in ['content-length', 'transfer-encoding']}
                resp_headers['Location'] = new_location

                # Return the redirect response with modified location
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
                generate_modified_stream(resp, request),
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