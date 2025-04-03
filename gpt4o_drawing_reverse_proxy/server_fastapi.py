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
    chunk_size = 8192  # 增大块大小以减少迭代次数
    try:
        async for chunk in response.content.iter_chunked(chunk_size):
            if chunk:  # 确保只发送非空数据块
                yield chunk
    except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError) as e:
        logger.error(f"Streaming error: {str(e)}")
        # 不再产生新的数据块，流会自然结束


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
    session = None
    response = None

    try:
        # 在函数内部创建session，确保作用域清晰
        timeout = aiohttp.ClientTimeout(total=60, connect=30, sock_read=30, sock_connect=30)
        session = aiohttp.ClientSession(
            timeout=timeout,
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

            # 使用自定义的背景任务管理器来处理资源清理
            # 创建一个副本以防response在流式传输期间被修改
            resp_copy = response
            session_copy = session

            # 实现一个cleanup函数，在流结束后关闭资源
            async def cleanup():
                await asyncio.sleep(1)  # 给流式传输一点开始时间
                try:
                    await resp_copy.release()
                except:
                    pass
                try:
                    await session_copy.close()
                except:
                    pass

            # 创建一个背景任务来处理清理工作
            cleanup_task = asyncio.create_task(cleanup())

            def on_response_end():
                # 确保不再引用全局变量
                if not cleanup_task.done():
                    cleanup_task.cancel()

            # 返回流式响应
            return StreamingResponse(
                stream_response_content(response),
                status_code=response.status,
                headers=response_headers,
                background=on_response_end
            )
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
            cookies_to_set = []
            for key, morsel in session.cookie_jar.filter_cookies(response.url).items():
                cookie_header = f"{key}={morsel.value}; Path=/"
                cookies_to_set.append(cookie_header)

            if cookies_to_set:
                response_headers["set-cookie"] = cookies_to_set

            # 等待关闭资源之前确保我们已经收到了所有数据
            return Response(
                content=content,
                status_code=response.status,
                headers=response_headers,
            )
    except asyncio.TimeoutError:
        logger.error(f"Request timed out for {target_url}")
        return Response(
            content="The request to the target server timed out. Please try again later.".encode(),
            status_code=504,
        )
    except aiohttp.ClientConnectorError:
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
        # 确保资源被正确释放
        try:
            if response:
                # 关闭响应，释放资源
                await response.release()
        except:
            pass
        try:
            if session:
                # 关闭会话
                await session.close()
        except:
            pass


parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", help="host")
parser.add_argument("--port", default=5001, help="port")
parser.add_argument("--workers", default=1, type=int, help="workers")
args = parser.parse_args()


def start_server(port=args.port, host=args.host):
    logger.info(f"Starting server at {host}:{port}")
    logger.info(f"Proxy target URL: {TARGET_URL}")

    # 配置更细致的日志
    logger.add("proxy_server.log", rotation="10 MB", level="DEBUG", backtrace=True, diagnose=True)

    # 增加 ASGI 应用的生命周期和超时设置
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        workers=args.workers,
        log_level="info",
        timeout_keep_alive=65,  # 提高keep-alive超时
        loop="auto"  # 让uvicorn自动选择最合适的事件循环
    )
    server = uvicorn.Server(config=config)
    try:
        server.run()
    finally:
        logger.info("Server shutdown.")


if __name__ == "__main__":
    fire.Fire(start_server)