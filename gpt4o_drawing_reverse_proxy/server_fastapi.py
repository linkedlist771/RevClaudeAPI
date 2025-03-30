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
        return await response.read()

    # Process HTML content
    content = await response.read()

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
@app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
async def proxy(request: Request, path: str = ""):
    logger.debug(f"path:\n{path}")

    # Create a client that will handle cookies properly
    async with httpx.AsyncClient(follow_redirects=False) as client:
        target_url = f"{TARGET_URL}/{path}"

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
            # Send request to target server
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body,
                cookies=cookies,  # Pass cookies directly
                follow_redirects=False
            )

            # Handle redirect responses
            if response.status_code in [301, 302, 303, 307, 308]:
                location = response.headers.get('Location', '')
                logger.debug(f"Redirect detected to: {location}")

                # If it's a relative URL, convert to absolute URL
                if location.startswith('/'):
                    # Stay on the same domain
                    location = f"{request.base_url.scheme}://{request.base_url.netloc}/{location.lstrip('/')}"
                elif location.startswith('http'):
                    # If it's an absolute URL to the target, rewrite it to point to our proxy
                    target_domain = TARGET_URL.split('//')[1]
                    if target_domain in location:
                        location = location.replace(
                            f"{TARGET_URL.split('//')[0]}//{target_domain}",
                            f"{request.base_url.scheme}://{request.base_url.netloc}"
                        )

                # Return redirect response to client with modified location
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding']}
                response_headers['Location'] = location

                return Response(
                    content=b"",
                    status_code=response.status_code,
                    headers=response_headers
                )

            # Check content type
            content_type = response.headers.get('Content-Type', '')

            # For streaming responses or non-HTML content, use StreamingResponse
            if ('text/html' not in content_type) or ('text/event-stream' in content_type):
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

                return Response(
                    content=content,
                    status_code=response.status_code,
                    headers=response_headers
                )

        except Exception as e:
            logger.error(f"Proxy error: {str(e)}")
            return Response(content=f"Error: {str(e)}".encode(), status_code=500)


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
    config = uvicorn.Config(app, host=host, port=port, workers=args.workers)
    server = uvicorn.Server(config=config)
    try:
        server.run()
    finally:
        logger.info("Server shutdown.")


if __name__ == '__main__':
    fire.Fire(start_server)