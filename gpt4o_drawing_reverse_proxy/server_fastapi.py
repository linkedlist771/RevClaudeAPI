from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import uvicorn
from starlette.background import BackgroundTask
from typing import Optional
import asyncio

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_URL = "https://gpt4oimagedrawing.585dg.com"

# 创建JavaScript文件目录
js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')
os.makedirs(js_dir, exist_ok=True)


# 读取JavaScript文件函数
def read_js_file(filename):
    file_path = os.path.join(js_dir, filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        # 如果文件不存在，创建默认内容
        default_content = "// Default content for " + filename
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(default_content)
        return default_content


# 提供list.js文件
@app.get('/list.js')
async def list_js():
    js_content = read_js_file('list.js')
    return Response(content=js_content, media_type='application/javascript')


# 处理响应内容的函数
async def process_response(response):
    content_type = response.headers.get('Content-Type', '')

    # 对于非HTML内容，直接返回
    if 'text/html' not in content_type:
        return await response.read()

    # 处理HTML内容
    content = await response.read()

    # 尝试解码内容
    try:
        html_content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            html_content = content.decode('latin-1')
        except Exception:
            return content

    # 注入JavaScript
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


# 主要代理路由
@app.route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
async def proxy(request: Request, path: str = ""):
    client = httpx.AsyncClient(follow_redirects=False)
    target_url = f"{TARGET_URL}/{path}"

    # 获取请求头和请求体代码保持不变
    # 获取请求头
    headers = {key: value for key, value in request.headers.items()
               if key.lower() not in ['host', 'content-length']}
    headers['Host'] = TARGET_URL.split('//')[1]
    headers['Accept-Encoding'] = 'identity'

    # 获取请求体
    body = await request.body()
    try:
        # 发送请求到目标服务器
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.query_params,
            content=body,
            cookies=request.cookies,
            follow_redirects=False
        )

        # 检查内容类型
        content_type = response.headers.get('Content-Type', '')

        # 对于流式响应或非HTML内容，使用StreamingResponse
        if ('text/html' not in content_type) or ('text/event-stream' in content_type):
            # 处理响应头
            response_headers = {key: value for key, value in response.headers.items()
                                if key.lower() not in ['content-length', 'transfer-encoding']}

            # 返回流式响应
            return StreamingResponse(
                response.aiter_bytes(),
                status_code=response.status_code,
                headers=response_headers,
                background=BackgroundTask(client.aclose)
            )
        else:
            # 对于HTML内容，保持原有处理方式
            content = await process_response(response)
            response_headers = {key: value for key, value in response.headers.items()
                                if key.lower() not in ['content-length', 'transfer-encoding', 'content-encoding']}
            await client.aclose()
            return Response(
                content=content,
                status_code=response.status_code,
                headers=response_headers
            )

    except Exception as e:
        await client.aclose()
        return Response(content=f"Error: {str(e)}", status_code=500)


# 根路径也使用代理
@app.route('/', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
async def root_proxy(request: Request):
    return await proxy(request, "")


if __name__ == '__main__':
    print("启动FastAPI反向代理服务器，监听0.0.0.0:5001...")
    print("JavaScript注入已启用，将注入 /list.js 到所有HTML响应")
    print(f"JavaScript文件目录: {js_dir}")
    uvicorn.run("main:app", host="0.0.0.0", port=5001, reload=True)