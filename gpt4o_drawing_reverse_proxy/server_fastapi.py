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
    start_time = time.time()
    logger.debug(f"Proxying request to path: {path}")
    logger.debug(f"Method: {request.method}")
    logger.debug(f"Client IP: {request.client.host if request.client else 'unknown'}")

    # Create a client with appropriate settings
    transport = httpx.AsyncHTTPTransport(retries=1)
    async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=30.0,
            transport=transport
    ) as client:
        target_url = f"{TARGET_URL}/{path}"
        logger.info(f"Target URL: {target_url}")

        # Get request body
        body = await request.body()

        # Get cookies from request
        cookies = request.cookies

        # Create browser-like headers
        browser_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Cache-Control': 'max-age=0',
            'Host': TARGET_URL.split('//')[1],
        }

        # Add referer for non-root requests
        if path:
            base_url = f"{request.base_url.scheme}://{request.base_url.netloc}"
            browser_headers['Referer'] = f"{base_url}/"

        # Override with any specific headers from the original request
        # Exclude some headers that should be controlled by our browser simulation
        excluded_headers = ['host', 'content-length', 'user-agent', 'accept', 'accept-encoding']
        for key, value in request.headers.items():
            if key.lower() not in excluded_headers:
                browser_headers[key] = value

        # Debug headers
        logger.debug(f"Request headers: {browser_headers}")
        logger.debug(f"Request cookies: {cookies}")

        try:
            # For POST requests, set appropriate Content-Type header
            if request.method == 'POST':
                content_type = request.headers.get('Content-Type', '')
                if content_type:
                    browser_headers['Content-Type'] = content_type

                logger.debug(f"POST request with Content-Type: {content_type}")

                # Attempt first session request to establish cookies/session
                # Some sites need an initial GET before accepting POSTs
                if not cookies:
                    logger.debug("Making initial GET request to establish session")
                    try:
                        init_response = await client.get(
                            TARGET_URL,
                            headers=browser_headers,
                            cookies=cookies,
                            follow_redirects=True
                        )
                        # Update cookies
                        cookies = {**cookies, **init_response.cookies}
                        logger.debug(f"Initial cookies: {cookies}")
                    except Exception as e:
                        logger.warning(f"Initial GET request failed: {e}")

            # Make the actual request
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=browser_headers,
                params=request.query_params,
                content=body,
                cookies=cookies,
                follow_redirects=False
            )

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            # For 403 responses, try to get more details
            if response.status_code == 403:
                logger.warning(f"403 Forbidden from {target_url}")
                try:
                    resp_body = await response.aread()
                    logger.debug(f"Full response body: {resp_body}")

                    # Check if there's any CloudFlare or security challenge
                    if b'captcha' in resp_body.lower() or b'cloudflare' in resp_body.lower() or b'challenge' in resp_body.lower():
                        logger.warning("Security challenge detected in response")
                except Exception as e:
                    logger.debug(f"Could not read full response body: {e}")

            # Handle redirects
            if response.status_code in [301, 302, 303, 307, 308]:
                location = response.headers.get('Location', '')
                logger.debug(f"Redirect detected to: {location}")

                # Rewrite location as needed
                if location.startswith('http'):
                    target_domain = TARGET_URL.split('//')[1]
                    if target_domain in location:
                        location = location.replace(
                            TARGET_URL,
                            f"{request.base_url.scheme}://{request.base_url.netloc}"
                        )
                elif location.startswith('/'):
                    location = f"{request.base_url.scheme}://{request.base_url.netloc}{location}"

                # Create response headers including cookies
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding']}
                response_headers['Location'] = location

                return Response(
                    content=b"",
                    status_code=response.status_code,
                    headers=response_headers
                )

            # Process content based on type
            content_type = response.headers.get('Content-Type', '')

            if 'text/event-stream' in content_type:
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding']}
                return StreamingResponse(
                    response.aiter_bytes(),
                    status_code=response.status_code,
                    headers=response_headers
                )
            else:
                content = await process_response(response)
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding', 'content-encoding']}

                # Add all cookies from response
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