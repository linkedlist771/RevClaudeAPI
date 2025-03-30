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

    # 创建一个自定义的重定向处理类
    class ProxyTransport(httpx.AsyncHTTPTransport):
        """自定义传输类，在重定向前处理URL"""

        async def handle_async_request(self, request):
            # 在请求发送前检查和修改URL
            logger.debug(f"Sending request to: {request.url}")
            return await super().handle_async_request(request)

    # 创建一个事件钩子来处理重定向
    def event_hook(response):
        # 记录重定向路径
        if response.history:  # 如果有重定向历史
            original_url = str(response.history[0].url)
            final_url = str(response.url)
            logger.info(f"Redirected from {original_url} to {final_url}")
        return response

    # 创建客户端，启用自动重定向
    async with httpx.AsyncClient(
            transport=ProxyTransport(),
            follow_redirects=True,  # 启用自动重定向
            timeout=30.0,
            event_hooks={'response': [event_hook]}
    ) as client:
        target_url = f"{TARGET_URL}/{path}"
        logger.info(f"Target URL: {target_url}")

        # 获取请求头
        headers = {key: value for key, value in request.headers.items()
                   if key.lower() not in ['host', 'content-length']}
        headers['Host'] = TARGET_URL.split('//')[1]
        headers['Accept-Encoding'] = 'identity'

        # 获取请求体
        body = await request.body()

        # 获取请求中的cookies
        cookies = request.cookies

        try:
            # 发送请求到目标服务器，让httpx自动处理重定向
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body,
                cookies=cookies
            )

            # 检查是否发生了重定向
            if response.history:
                logger.info(f"Request was redirected {len(response.history)} times")
                for hist in response.history:
                    logger.debug(f"Redirect: {hist.status_code} - {hist.url}")

            # 检查内容类型
            content_type = response.headers.get('Content-Type', '')
            logger.debug(f"content_type:{content_type}")

            # 对于流式响应，使用StreamingResponse
            if ('text/event-stream' in content_type):
                # 处理响应头
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding']}

                # 返回流式响应
                return StreamingResponse(
                    response.aiter_bytes(),
                    status_code=response.status_code,
                    headers=response_headers
                )
            else:
                # 对于HTML内容，使用现有的处理方法
                # 这里不能直接使用response.read()因为内容可能已被读取
                content = await process_response(response)
                response_headers = {key: value for key, value in response.headers.items()
                                    if key.lower() not in ['content-length', 'transfer-encoding', 'content-encoding']}

                return Response(
                    content=content,
                    status_code=response.status_code,
                    headers=response_headers
                )

        except Exception as e:
            # 异常处理部分保持不变
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