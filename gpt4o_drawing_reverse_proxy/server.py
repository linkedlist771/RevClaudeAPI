import asyncio
import os
from datetime import datetime, timedelta
import requests
from flask import (Flask, Response, jsonify, make_response, redirect, request,
                   send_file, send_from_directory, stream_with_context)
from loguru import logger
from utils import get_souruxgpt_manager
from configs import ROOT, JS_DIR, TARGET_URL
from sync_base_redis_manager import FlaskUserRecordManager

logger.add("log_file.log", rotation="1 week")  # 每周轮换一次文件

app = Flask(__name__)

# Initialize Redis manager
user_record_manager = FlaskUserRecordManager()

# Helper function to extract account from login request
def extract_account_from_request(request):
    return request.form["account"]

# Helper function to extract cookies
def extract_cookies(cookie_header):
    if not cookie_header:
        return {}
    cookies = {}
    parts = cookie_header.split("; ")
    for part in parts:
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name] = value
    return cookies

# Function to read JavaScript files
def read_js_file(filename):
    file_path = os.path.join(JS_DIR, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        # If file doesn't exist, create it with default content
        default_content = "// Default content for " + filename
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(default_content)
        return default_content

# 提供list.js文件
@app.route("/list.js")
def list_js():
    js_content = read_js_file("list.js")
    return Response(js_content, mimetype="application/javascript")

@app.route("/editPassword", methods=["POST"])
def edit_password():
    gpt_manager = asyncio.run(get_souruxgpt_manager())
    data = request.get_json()
    # 获取请求参数
    account = data.get("account")
    password = data.get("password")
    new_password = data.get("new_password")
    # 验证参数
    if not account or not password or not new_password:
        return (
            jsonify(
                {"status": "error", "message": "缺少必要参数：account、password 或 new_password"}
            ),
            400,
        )
    success = asyncio.run(gpt_manager.change_password(account, password, new_password))
    if success:
        return jsonify({"status": "success", "message": "密码修改成功"})
    else:
        return jsonify({"status": "error", "message": "密码修改失败，请检查用户名和密码是否正确"}), 400

@app.route("/usage_stats", methods=["POST"])
def usage_stats():
    try:
        data = request.get_json()
        account = data.get("account")

        if account:
            result = user_record_manager.get_usage_stats(account)
        else:
            result = user_record_manager.get_usage_stats()

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in usage_stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


# 处理所有请求的主要函数
@app.route(
    "/",
    defaults={"path": ""},
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy(path):
    # 构建目标URL
    target_url = f"{TARGET_URL}/{path}"
    # 获取所有请求头
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ["host", "content-length"]
    }
    headers["Host"] = TARGET_URL.split("//")[1]
    headers["Accept-Encoding"] = "identity"
    params = request.args.to_dict()
    data = request.get_data()
    is_conversation_request = (
        "backend-api/conversation" in path and request.method == "POST"
    )
    is_login_request = request.method == "POST" and path == "login"


    account = None
    if is_login_request:
        account = extract_account_from_request(request)
    try:
        # 使用适当的方法发送请求
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=params,
            data=data,
            cookies=request.cookies,
            allow_redirects=False,
            stream=True,
        )
        response_headers = {
            key: value
            for key, value in resp.headers.items()
            if key.lower()
            not in ["content-length", "transfer-encoding", "content-encoding"]
        }

        if is_conversation_request and "Cookie" in headers:
            cookie_str = headers["Cookie"]
            extracted_cookies = extract_cookies(cookie_str)

            # 检查是否包含 gfsessionid
            if "gfsessionid" in extracted_cookies:
                gfsessionid = extracted_cookies["gfsessionid"]
                user_record_manager.update_usage_for_gfsessionid(gfsessionid)

        # 处理登录响应，绑定gfsessionid到账户
        if is_login_request and account and "Set-Cookie" in resp.headers:
            cookies = resp.headers["Set-Cookie"]
            extracted_cookies = extract_cookies(cookies)

            if "gfsessionid" in extracted_cookies:
                gfsessionid = extracted_cookies["gfsessionid"]
                user_record_manager.bind_gfsessionid_to_account(account, gfsessionid)
            # 检查是否已经包含 SameSite 或 Secure 属性，不包含则追加
            if "SameSite" not in cookies:
                cookies += "; SameSite=None"
            if "Secure" not in cookies:
                cookies += "; Secure"
            response_headers["Set-Cookie"] = cookies

        # 创建一个函数来处理响应内容
        def generate():
            # 对于非HTML内容，直接流式传
            all_content = b""
            if "text/html" not in resp.headers.get("Content-Type", ""):
                for chunk in resp.iter_content(chunk_size=1024):
                    # if is_conversation_request:
                    #     logger.debug(f"chunk:\n{chunk}")
                    all_content += chunk
                    yield chunk

                try :
                    all_content = all_content.decode("utf-8")
                except:
                    all_content = all_content.decode("latin-1")
                if "download" in path:
                    logger.debug(f"download path:\n{path}")
                    logger.debug(f"all_content:\n{all_content}")
                return



            content = b""
            for chunk in resp.iter_content(chunk_size=1024):
                content += chunk

            try:
                html_content = content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    html_content = content.decode("latin-1")
                except Exception:
                    yield content
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
                        + html_content[body_end + 1 :]
                    )
            else:
                html_content = '<script src="/list.js"></script>' + html_content

            yield html_content.encode("utf-8")

        # 创建Flask响应对象
        flask_response = Response(
            stream_with_context(generate()),
            status=resp.status_code,
            headers=response_headers,
        )

        return flask_response

    except requests.RequestException as e:
        # 处理请求错误
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="启动反向代理服务器")
    parser.add_argument("--port", type=int, default=5001, help="端口号")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="主机地址")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=True, threaded=True)
