import asyncio
import json
import requests
from configs import IMAGES_DIR, JS_DIR, ROOT, SERVER_BASE_URL, TARGET_URL
from flask import (Flask, Response, jsonify, make_response, redirect, request,
                   send_file, send_from_directory, stream_with_context)
from loguru import logger
from sync_base_redis_manager import FlaskUserRecordManager
from utils import (extract_account_from_request, extract_cookies,
                   get_souruxgpt_manager, read_js_file, save_image_from_dict)

logger.add("log_file.log", rotation="1 week")  # 每周轮换一次文件

app = Flask(__name__)

user_record_manager = FlaskUserRecordManager()


# 提供图片文件的路由
@app.route("/images/<path:file_path>")
def serve_image(file_path):
    return send_from_directory(IMAGES_DIR, file_path)


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
        page = int(data.get("page", 1))  # Default to page 1
        page_size = int(data.get("page_size", 10))  # Default to 10 items per page

        if account:
            result = user_record_manager.get_usage_stats(
                account, page=page, page_size=page_size
            )
        else:
            result = user_record_manager.get_usage_stats(page=page, page_size=page_size)

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
    target_url = f"{TARGET_URL}/{path}"
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
    is_user_uploaded_image = "backend-api/files/process_upload_stream" in path

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
        if is_user_uploaded_image:
            logger.debug(f"resp.content:\n{resp.content}")
            response_json = json.loads(resp.content.decode("utf-8"))
            # 获取file id 这个变量
            file_id = response_json.get("file_id")
            logger.debug(f"用户上传file_id:\n{file_id}")
            if file_id:
                user_record_manager.add_uploaded_file_id(file_id)
                logger.debug(f"Added file_id {file_id} to shared uploaded files list")


        if is_conversation_request and "Cookie" in headers:
            cookie_str = headers["Cookie"]
            extracted_cookies = extract_cookies(cookie_str)
            if "gfsessionid" in extracted_cookies:
                gfsessionid = extracted_cookies["gfsessionid"]
                user_record_manager.update_usage_for_gfsessionid(gfsessionid)
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

                try:
                    all_content = all_content.decode("utf-8")
                except:
                    all_content = all_content.decode("latin-1")
                if "download" in path:
                    logger.debug(f"download path:\n{path}")
                    logger.debug(f"all_content:\n{all_content}")
                    content_dict = json.loads(all_content)
                    file_id = content_dict.get("file_id")
                    
                    # Check if this is a user-uploaded file
                    if file_id and user_record_manager.is_uploaded_file(file_id):
                        logger.debug(f"Skipping download for user-uploaded file: {file_id}")
                        return
                    file_name, save = save_image_from_dict(content_dict)
                    cookies = request.cookies
                    if "gfsessionid" in cookies and save:
                        gfsessionid = cookies["gfsessionid"]
                        image_url = f"{SERVER_BASE_URL}/images/{file_name}"
                        user_record_manager.add_image_to_account_by_gfsessionid(
                            gfsessionid, image_url
                        )
                        logger.debug(
                            f"图片已添加到用户账号, gfsessionid: {gfsessionid}, image_url: {image_url}"
                        )
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
