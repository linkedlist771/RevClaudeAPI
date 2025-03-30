from flask import Flask, request, Response, stream_with_context
import requests
from bs4 import BeautifulSoup
import re
import gzip
import brotli
import zlib
from io import BytesIO
import os
from flask import Flask, request, Response, jsonify
from flask import Flask, request, Response, send_from_directory
from flask import Flask, request, make_response, jsonify, redirect
from datetime import datetime, timedelta

import requests
import pymysql
import logging
import pymysql.cursors
from datetime import datetime
from flask import Flask, request, jsonify, send_file
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import quote
import json
import re
import uuid
import os
import chardet
from bs4 import BeautifulSoup
import traceback
import time

app = Flask(__name__)

TARGET_URL = "https://gpt4oimagedrawing.585dg.com"

# Create a directory for JavaScript files if it doesn't exist
js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')
os.makedirs(js_dir, exist_ok=True)


# Function to read JavaScript files
def read_js_file(filename):
    file_path = os.path.join(js_dir, filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        # If file doesn't exist, create it with default content
        default_content = "// Default content for " + filename
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(default_content)
        return default_content


# 提供list.js文件
@app.route('/list.js')
def list_js():
    js_content = read_js_file('list.js')
    return Response(js_content, mimetype='application/javascript')

# 处理所有请求的主要函数
@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy(path):
    # 构建目标URL
    target_url = f"{TARGET_URL}/{path}"

    # 获取所有请求头
    headers = {key: value for key, value in request.headers.items()
               if key.lower() not in ['host', 'content-length']}
    headers['Host'] = TARGET_URL.split('//')[1]

    # 关键修改：不要接受压缩内容，这样我们就能正确处理响应
    headers['Accept-Encoding'] = 'identity'

    # 处理请求参数
    params = request.args.to_dict()

    # 获取请求体
    data = request.get_data()

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
            stream=True
        )

        # 创建一个函数来处理响应内容
        def generate():
            # 对于非HTML内容，直接流式传输
            if 'text/html' not in resp.headers.get('Content-Type', ''):
                for chunk in resp.iter_content(chunk_size=1024):
                    yield chunk
                return

            # 对于HTML内容，完整收集然后处理
            content = b''
            for chunk in resp.iter_content(chunk_size=1024):
                content += chunk

            # 尝试解码内容
            try:
                html_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    # 尝试其他编码
                    html_content = content.decode('latin-1')
                except Exception:
                    # 如果所有尝试都失败，返回原始内容
                    yield content
                    return

            # 注入JavaScript
            if '</head>' in html_content:
                html_content = html_content.replace('</head>', '<script src="/list.js"></script></head>')
            elif '<body' in html_content:
                body_pos = html_content.find('<body')
                body_end = html_content.find('>', body_pos)
                if body_end != -1:
                    html_content = html_content[:body_end + 1] + '<script src="/list.js"></script>' + html_content[
                                                                                                      body_end + 1:]
            else:
                html_content = '<script src="/list.js"></script>' + html_content

            # 返回修改后的内容
            yield html_content.encode('utf-8')

        # 处理响应头，复制原始头，但排除某些特定的头
        response_headers = {key: value for key, value in resp.headers.items()
                            if key.lower() not in ['content-length', 'transfer-encoding', 'content-encoding']}

        # 创建Flask响应对象
        flask_response = Response(
            stream_with_context(generate()),
            status=resp.status_code,
            headers=response_headers
        )

        return flask_response

    except requests.RequestException as e:
        # 处理请求错误
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    print("启动反向代理服务器，监听0.0.0.0:5000...")
    print("JavaScript注入已启用，将注入 /list.js 到所有HTML响应")
    print(f"JavaScript文件目录: {js_dir}")
    # 在生产环境中，你可能需要使用更强大的WSGI服务器如Gunicorn
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)