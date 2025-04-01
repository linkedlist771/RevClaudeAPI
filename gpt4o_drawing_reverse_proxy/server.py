import asyncio

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
import logging
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
from bs4 import BeautifulSoup
import traceback
import time
from loguru import logger
from utils import get_souruxgpt_manager

app = Flask(__name__)

TARGET_URL = "https://soruxgpt-saas-liuli.soruxgpt.com"

# Create a directory for JavaScript files if it doesn't exist
js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')
os.makedirs(js_dir, exist_ok=True)

import sqlite3
from functools import wraps

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('user_stats.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        account TEXT PRIMARY KEY,
        cookie TEXT,
        usage_count INTEGER DEFAULT 0,
        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

# Call init_db at startup
init_db()

# Database helper functions
def bind_gfsessionid_to_account(account, gfsessionid):
    """Bind a gfsessionid to an account"""
    try:
        conn = sqlite3.connect('user_stats.db')
        cursor = conn.cursor()
        
        # Check if account already exists
        cursor.execute("SELECT * FROM users WHERE account = ?", (account,))
        user = cursor.fetchone()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if user:
            # Update existing account
            cursor.execute(
                "UPDATE users SET cookie = ?, last_used = ? WHERE account = ?",
                (gfsessionid, current_time, account)
            )
        else:
            # Create new account
            cursor.execute(
                "INSERT INTO users (account, cookie, usage_count, last_used) VALUES (?, ?, ?, ?)",
                (account, gfsessionid, 0, current_time)
            )
        
        conn.commit()
        conn.close()
        logger.debug(f"Successfully bound gfsessionid to account: {account}")
        return True
    except Exception as e:
        logger.error(f"Error binding gfsessionid to account: {str(e)}")
        return False

def update_usage_for_gfsessionid(gfsessionid):
    """Update usage count for an account based on gfsessionid"""
    try:
        conn = sqlite3.connect('user_stats.db')
        cursor = conn.cursor()
        
        # Find account by gfsessionid
        cursor.execute("SELECT account FROM users WHERE cookie = ?", (gfsessionid,))
        account = cursor.fetchone()
        
        if account:
            account = account[0]
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Update usage count and last_used
            cursor.execute(
                "UPDATE users SET usage_count = usage_count + 1, last_used = ? WHERE account = ?",
                (current_time, account)
            )
            
            conn.commit()
            conn.close()
            logger.debug(f"Updated usage count for account: {account}")
            return True
        else:
            conn.close()
            logger.warning(f"No account found for gfsessionid: {gfsessionid}")
            return False
    except Exception as e:
        logger.error(f"Error updating usage count: {str(e)}")
        return False

def get_account_by_gfsessionid(gfsessionid):
    """Get account information by gfsessionid"""
    try:
        conn = sqlite3.connect('user_stats.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE cookie = ?", (gfsessionid,))
        user = cursor.fetchone()
        
        conn.close()
        
        if user:
            return dict(user)
        return None
    except Exception as e:
        logger.error(f"Error getting account by gfsessionid: {str(e)}")
        return None

# Helper function to extract account from login request
def extract_account_from_request(request):
    return request.form['account']

# Helper function to extract cookies
def extract_cookies(cookie_header):
    if not cookie_header:
        return {}
    cookies = {}
    parts = cookie_header.split('; ')
    for part in parts:
        if '=' in part:
            name, value = part.split('=', 1)
            cookies[name] = value
    return cookies


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


# 提供yulan.js文件
@app.route('/yulan.js')
def yulan_js():
    js_content = read_js_file('yulan.js')
    return Response(js_content, mimetype='application/javascript')

@app.route('/editPassword', methods=['POST'])
def edit_password():
    gpt_manager = asyncio.run(get_souruxgpt_manager())
    data = request.get_json()
    # 获取请求参数
    account = data.get('account')
    password = data.get('password')
    new_password = data.get('new_password')
    # 验证参数
    if not account or not password or not new_password:
        return jsonify({
            'status': 'error',
            'message': '缺少必要参数：account、password 或 new_password'
        }), 400
    success = asyncio.run(gpt_manager.change_password(account, password, new_password))
    if success:
        return jsonify({
            'status': 'success',
            'message': '密码修改成功'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': '密码修改失败，请检查用户名和密码是否正确'
        }), 400


@app.route('/usage_stats', methods=['POST'])
def usage_stats():
    try:
        data = request.get_json()
        account = data.get('account')

        if account:
            # Get stats for specific account using a helper function
            conn = sqlite3.connect('user_stats.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT account, usage_count, last_used FROM users WHERE account = ?", (account,))
            row = cursor.fetchone()
            conn.close()

            if row:
                result = {
                    'account': row['account'],
                    'usage_count': row['usage_count'],
                    'last_used': row['last_used']
                }
            else:
                result = {'message': f'No data found for account: {account}'}
        else:
            # If no identifiers provided, return all stats
            conn = sqlite3.connect('user_stats.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT account, usage_count, last_used FROM users ORDER BY usage_count DESC")
            rows = cursor.fetchall()
            conn.close()

            stats = [{
                'account': row['account'],
                'usage_count': row['usage_count'],
                'last_used': row['last_used']
            } for row in rows]
            result = stats

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in usage_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/batch_usage_stats', methods=['POST'])
def batch_usage_stats():
    try:
        data = request.get_json()
        accounts = data.get('accounts', [])
        
        if not accounts or not isinstance(accounts, list):
            return jsonify({'error': 'Invalid or missing accounts parameter'}), 400
            
        results = {}
        conn = sqlite3.connect('user_stats.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        for account in accounts:
            cursor.execute("SELECT account, usage_count, last_used FROM users WHERE account = ?", (account,))
            row = cursor.fetchone()
            
            if row:
                results[account] = {
                    'account': row['account'],
                    'usage_count': row['usage_count'],
                    'last_used': row['last_used']
                }
            else:
                results[account] = {'message': f'No data found'}
        
        conn.close()
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in batch_usage_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/top_users', methods=['GET'])
def top_users():
    try:
        limit = request.args.get('limit', default=10, type=int)
        users = get_top_users(limit)
        
        # Filter out cookie information for security
        for user in users:
            if 'cookie' in user:
                del user['cookie']
        
        return jsonify(users)
    except Exception as e:
        logger.error(f"Error in top_users: {str(e)}")
        return jsonify({'error': str(e)}), 500



def get_top_users(limit=10):
    """Get top users by usage count"""
    try:
        conn = sqlite3.connect('user_stats.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT account, cookie, usage_count, last_used FROM users ORDER BY usage_count DESC LIMIT ?", 
            (limit,)
        )
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting top users: {str(e)}")
        return []


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

    # Check if this is a conversation API request
    is_conversation_request = "backend-api/conversation" in path and request.method == 'POST'
    
    # Check if this is a login request
    is_login_request = request.method == 'POST' and path == 'login'
    account = None
    if is_login_request:
        account = extract_account_from_request(request)

    # logger.debug(path)

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

        # 处理响应头，复制原始头，但排除某些特定的头
        response_headers = {key: value for key, value in resp.headers.items()
                            if key.lower() not in ['content-length', 'transfer-encoding', 'content-encoding']}

        # Update usage count for conversation API requests
        if is_conversation_request and 'Cookie' in headers:
            cookie_str = headers['Cookie']
            extracted_cookies = extract_cookies(cookie_str)
            
            # 检查是否包含 gfsessionid
            if 'gfsessionid' in extracted_cookies:
                gfsessionid = extracted_cookies['gfsessionid']
                update_usage_for_gfsessionid(gfsessionid)
        
        # 处理登录响应，绑定gfsessionid到账户
        if is_login_request and account and 'Set-Cookie' in resp.headers:
            cookie_str = resp.headers['Set-Cookie']
            extracted_cookies = extract_cookies(cookie_str)
            
            if 'gfsessionid' in extracted_cookies:
                gfsessionid = extracted_cookies['gfsessionid']
                bind_gfsessionid_to_account(account, gfsessionid)

        # 如果存在 Set-Cookie，则追加 SameSite=None; Secure
        # 进行iframe打开
        if 'Set-Cookie' in response_headers:
            # 假设 Set-Cookie 只有一个值。如果有多个值，需要分别处理
            cookies = response_headers['Set-Cookie']
            # 检查是否已经包含 SameSite 或 Secure 属性，不包含则追加
            if 'SameSite' not in cookies:
                cookies += '; SameSite=None'
            if 'Secure' not in cookies:
                cookies += '; Secure'
            response_headers['Set-Cookie'] = cookies

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
    import argparse
    parser = argparse.ArgumentParser(description='启动反向代理服务器')
    parser.add_argument('--port', type=int, default=5001, help='端口号')
    args = parser.parse_args()
    # print("启动反向代理服务器，监听0.0.0.0:5001...")
    # print("JavaScript注入已启用，将注入 /list.js 到所有HTML响应")
    # print(f"JavaScript文件目录: {js_dir}")
    # 在生产环境中，你可能需要使用更强大的WSGI服务器如Gunicorn
    app.run(host='0.0.0.0', port=args.port, debug=True, threaded=True)