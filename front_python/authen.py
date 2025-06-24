import hashlib
import json
from datetime import datetime, time, timedelta

import redis
import streamlit as st
from streamlit import runtime
from streamlit.runtime.scriptrunner import get_script_run_ctx

from front_configs import ADMIN_PASSWORD, ADMIN_USERNAME, redis_client


def get_remote_ip():
    try:
        ctx = get_script_run_ctx()
        if ctx is None:
            return None
        session_info = runtime.get_instance().get_client(ctx.session_id)
        if session_info is None:
            return None
        return session_info.request.remote_ip
    except Exception as e:
        return None


def get_device_hash():
    """获取当前会话的哈希值"""
    # 使用session_id作为唯一标识
    return hashlib.md5(get_remote_ip().encode()).hexdigest()


def check_password():
    """Returns `True` if the user has the correct password."""

    def verify_login(username, password):
        """验证用户输入的密码"""
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            device_hash = get_device_hash()
            # 在Redis中设置登录状态
            login_data = {
                "is_logged_in": True,
                "timestamp": datetime.now().timestamp(),
                "device_hash": device_hash,
                "username": username,
            }
            redis_client.setex(
                f"login:{username}:{device_hash}",
                7 * 24 * 60 * 60,  # 7天过期
                json.dumps(login_data),
            )
            return True
        return False

    # 检查Redis中的登录状态
    device_hash = get_device_hash()
    login_data = redis_client.get(f"login:{ADMIN_USERNAME}:{device_hash}")

    if login_data:
        login_data = json.loads(login_data)
        current_time = datetime.now().timestamp()
        one_week = 7 * 24 * 60 * 60  # 一周的秒数

        if (
            login_data.get("is_logged_in")
            and current_time - login_data["timestamp"] < one_week
        ):
            return True

    # 显示登录表单

    # 创建一个表单，用于用户登录
    with st.form("login_form"):
        # 用户名输入框
        username = st.text_input("用户名")

        # 密码输入框，输入类型为密码
        password = st.text_input("密码", type="password")

        # 登录按钮
        submit = st.form_submit_button("登录")

        # 当用户点击登录按钮时执行验证
        if submit:
            if verify_login(username, password):
                st.success("登录成功！")
                # 重新运行应用以显示登录后的内容
                # 重新刷新下
                # st.experimental_rerun()  # 重新运行应用以显示登录后的内容
                st.success("刷新页面即可")
            else:
                st.error("😕 用户名或密码错误")
                return False
    return False
