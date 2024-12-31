import asyncio
import hashlib
import json
from datetime import datetime, timedelta, time
import requests
import json
from typing import List
import os
import time
from loguru import logger
from datetime import datetime
import pytz
from httpx import AsyncClient
import redis
import streamlit as st
import pandas as pd
import altair as alt
from tqdm import tqdm
from urllib.request import urlopen
import plotly.express as px

from front_utils import create_sorux_accounts
from front_configs import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    CLAUDE_BACKEND_API_BASE_URL,
    CLAUDE_BACKEND_API_USER_URL,
    CLAUDE_BACKEND_API_APIAUTH,
)

# running:  streamlit run front_python/front_manager.py --server.port 5000


st.set_page_config(page_title="API密钥和Cookie管理")


def get_all_devices():
    url = f"{CLAUDE_BACKEND_API_BASE_URL}/devices/all_token_devices"
    headers = {"User-Agent": "Apifox/1.0.0 (https://apifox.com)"}
    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except:
        return None


def logout_device(token, user_agent):
    url = f"{CLAUDE_BACKEND_API_BASE_URL}/devices/logout"
    headers = {"Authorization": token, "User-Agent": user_agent}
    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except:
        return None


def get_device_type(user_agent):
    ua = user_agent.lower()
    if "iphone" in ua:
        return "iPhone"
    elif "android" in ua:
        return "Android"
    elif "windows" in ua:
        return "Windows"
    elif "macintosh" in ua:
        return "MacOS"
    else:
        return "Other"


def initialize_session_state(data):
    if "data" not in st.session_state:
        st.session_state["data"] = data
    if "search_token" not in st.session_state:
        st.session_state["search_token"] = ""
    if "logout_messages" not in st.session_state:
        st.session_state["logout_messages"] = {}


def get_api_stats():
    # 添加一个切换按钮来选择 usage_type
    usage_type = st.radio(
        "选择统计类型",
        ["token_usage", "record_usage"],
        format_func=lambda x: "Token使用统计" if x == "token_usage" else "记录使用统计",
    )

    url = f"http://54.254.143.80:8090/token_stats?usage_type={usage_type}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()["data"]
        else:
            st.error("获取数据失败")
            return None
    except Exception as e:
        st.error(f"请求错误: {str(e)}")
        return None


def create_dataframe(data):
    records = []
    for item in data:
        record = {
            "token": item["token"],
            "total_usage": item["usage"]["total"],
            "last_3_hours": item["usage"]["last_3_hours"],
            "last_12_hours": item["usage"]["last_12_hours"],
            "last_24_hours": item["usage"]["last_24_hours"],
            "last_week": item["usage"]["last_week"],
            "current_active": item["current_active"],
            "last_seen_seconds": item.get("last_seen_seconds", 0),
        }
        records.append(record)
    return pd.DataFrame(records)


# Redis 连接设置
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit import runtime


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


def set_cn_time_zone():
    """设置当前进程的时区为中国时区"""
    os.environ["TZ"] = "Asia/Shanghai"
    try:
        time.tzset()
        logger.info("Set time zone to Asia/Shanghai.")
    except Exception as e:
        logger.error(f"Failed to set time zone: {e}")


def build_client_headers() -> dict:
    headers = {
        "APIAUTH": CLAUDE_BACKEND_API_APIAUTH,
        "Content-Type": "application/json",
    }
    return headers


set_cn_time_zone()


def delete_sessions(ids: List[int]):
    url = f"{CLAUDE_BACKEND_API_USER_URL}/delete"
    payload = json.dumps({"ids": ids})
    headers = build_client_headers()
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code != 200:
        raise Exception(
            f"Failed to delete sessions. Status code: {response.status_code}"
        )


async def get_api_key_information(api_key: str):
    async with AsyncClient() as client:
        headers = build_client_headers()
        url = f"{CLAUDE_BACKEND_API_USER_URL}/page/"
        payload = {"page": 1, "size": 20, "keyWord": api_key}
        res = await client.post(url, headers=headers, json=payload, timeout=60)
        res_json = res.json()
        data = res_json.get("data")
        data = data["list"]
        result = next((i for i in data if i.get("userToken") == api_key), None)
        return result


async def get_all_api_key_information(user_tokens: List[str]):
    tasks = [get_api_key_information(token) for token in user_tokens]
    return await asyncio.gather(*tasks)


def delete_batch_user_tokens(user_tokens: List[str], batch_size: int = 50):
    # Get all user data asynchronously
    user_infos = asyncio.run(get_all_api_key_information(user_tokens))
    # Extract IDs from user info
    ids_to_delete = [
        user_info.get("id")
        for user_info in user_infos
        if user_info and user_info.get("id")
    ]

    # Delete in batches
    for i in range(0, len(ids_to_delete), batch_size):
        batch = ids_to_delete[i : i + batch_size]
        delete_sessions(batch)
    message = f"Deleted a total of {len(ids_to_delete)} sessions"
    return message


import time


# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = {}


def main():
    # 设置页面标题

    # 设置页面标题
    st.title("API密钥和Cookie管理")

    # 在左侧边栏添加主要功能选择
    main_function = st.sidebar.radio("主要功能", ["API密钥管理", "Cookie管理"])

    if main_function == "API密钥管理":
        # API密钥管理部分
        api_key_function = st.sidebar.radio(
            "API密钥管理",
            [
                "创建API密钥",
                "查看API密钥使用情况",
                "查看API设备使用情况",
                "批量删除API密钥",  # 新增这一行
                "获取所有API密钥",
                "重置API密钥使用量",  # Add this line
                "延长API密钥过期时间",  # 新增这一行
            ],
        )

        if api_key_function == "创建API密钥":
            st.subheader("创建API密钥")

            # 基本设置
            col1, col2 = st.columns(2)
            with col1:
                key_type = st.text_input("密钥类型", value="plus")
                key_number = st.number_input("密钥数量", min_value=1, value=1, step=1)
            with col2:
                expiration_days = st.number_input(
                    "过期天数", min_value=0, value=0, step=1
                )
                expiration_hours = st.number_input(
                    "过期小时数(只有Claude支持小数)",
                    min_value=0.1,  # 最小值改为0.1小时(6分钟)
                    value=1.0,  # 默认值
                    step=1.0,  # 步进值改为0.1
                    format="%.1f",  # 显示1位小数
                )

            # 速率限制设置
            st.markdown("### 速率限制")
            col3, col4 = st.columns(2)
            with col3:
                message_limited = st.number_input(
                    "消息速率限速条数", min_value=1, value=5, step=1
                )
                rate_refresh_time = st.number_input(
                    "消息速率限速时间(分钟)", min_value=1, value=1, step=1
                )
            with col4:
                message_bucket_sum = st.number_input(
                    "消息总量限制", min_value=1, value=100, step=1
                )
                message_bucket_time = st.number_input(
                    "消息总量限速时间(分钟)", min_value=1, value=180, step=1
                )

            # 使用类型设置
            st.markdown("### 使用范围")
            options = [
                "🔒 只适用于claude账号池镜像",
                "🌐 只适用于逆向网站",
                "🔁 全部设为都使用",
                "🤖 适用于ChatGPT镜像",
                "🔄 只用于claude账号池续费",
            ]
            selected_option = st.selectbox("选择使用类型", options)

            total_hours = expiration_days * 24 + expiration_hours
            expiration_days_float = total_hours / 24

            if st.button("创建API密钥"):
                api_keys = []
                sorux_accounts = []

                # if selected_option == "🔄 只用于claude账号池续费":
                if selected_option in [options[-1]]:
                    url = f"{BASE_URL}/api/v1/renewal/create"
                    payload = {
                        "days": expiration_days,
                        "hours": expiration_hours,
                        "minutes": 0,
                        "count": key_number,
                    }
                    response = requests.post(url, json=payload)
                    if response.status_code == 200:
                        renewal_codes = response.json()
                        st.success("续费码创建成功")
                        # 显示续费码
                        renewal_codes_str = "\n".join(renewal_codes)
                        st.text_area("续费码", renewal_codes_str)
                        st.code(
                            json.dumps(
                                {"renewal_codes": renewal_codes},
                                indent=4,
                                ensure_ascii=False,
                            ),
                            language="json",
                        )

                else:
                    if selected_option in [options[0], options[2]]:
                        url = f"{API_KEY_ROUTER}/create_key"
                        payload = {
                            "expiration_days": expiration_days_float,
                            "key_type": key_type,
                            "key_number": key_number,
                        }
                        response = requests.post(url, json=payload)
                        if response.status_code == 200:
                            api_keys = response.json().get("api_key", [])

                    # Create SoruxGPT accounts if needed
                    if selected_option in [options[3], options[2]]:
                        sorux_accounts = asyncio.run(
                            create_sorux_accounts(
                                key_number,
                                int(total_hours),
                                message_limited,
                                rate_refresh_time,
                                message_bucket_sum,
                                message_bucket_time,
                            )
                        )

                progress_bar = st.progress(0)
                status = st.empty()

                # Process official API keys
                if api_keys:
                    expire_date = datetime.now() + timedelta(hours=total_hours)
                    expire_time = expire_date.strftime("%Y-%m-%d %H:%M:%S")
                    is_plus = 1 if key_type == "plus" else 0

                    total_keys = len(api_keys)
                    for index, api_key in enumerate(api_keys, start=1):
                        progress = int(index / total_keys * 100)
                        progress_bar.progress(progress)
                        status.text(
                            f"正在处理 API 密钥 {index}/{total_keys}: {api_key}"
                        )

                        if selected_option != options[1]:  # Not "只适用于逆向网站"
                            new_payload = {
                                "userToken": api_key,
                                "expireTime": expire_time,
                                "isPlus": is_plus,
                            }

                            new_headers = build_client_headers()
                            new_response = requests.post(
                                f"{CLAUDE_BACKEND_API_USER_URL}/add",
                                json=new_payload,
                                headers=new_headers,
                            )
                            logger.debug(new_response.text)

                # Display results
                if api_keys:
                    st.success("API密钥创建成功。")
                    formatted_json = json.dumps(
                        {"api_key": api_keys}, indent=4, ensure_ascii=False
                    )
                    api_key_str = "\n".join(api_keys)
                    st.text_area("API Key", api_key_str)

                    st.code(formatted_json, language="json")

                if sorux_accounts:
                    st.success("SoruxGPT账号创建成功。")
                    formatted_accounts = "\n".join(
                        [account["formatted"] for account in sorux_accounts]
                    )
                    st.code(formatted_accounts, language="text")

                # Delete API keys if only reverse proxy is needed
                if selected_option == options[1] and api_keys:
                    delete_url = f"{API_KEY_ROUTER}/delete_batch_keys"
                    delete_payload = {"api_keys": api_keys}
                    delete_response = requests.delete(delete_url, json=delete_payload)

        elif api_key_function == "批量删除API密钥":
            st.subheader("批量删除API密钥")
            api_keys_to_delete = st.text_area(
                "输入要删除的API密钥（每行一个或用逗号分隔）"
            )
            # default as the api key
            delete_type = st.selectbox("选择删除类型", ["API密钥", "续费码"], index=0)
            # 先按换行符分割，然后对每个部分按逗号分割，最后去除空白
            api_keys_to_delete = api_keys_to_delete.replace('"', "")
            api_keys_to_delete = api_keys_to_delete.replace("'", "")
            api_keys_list = [
                key.strip()
                for line in api_keys_to_delete.split("\n")
                for key in line.split(",")
                if key.strip()
            ]

            if st.button("批量删除API密钥"):
                if delete_type == "API密钥":

                    if api_keys_list:
                        try:
                            message = delete_batch_user_tokens(api_keys_list)
                            st.success(message)
                        except Exception as e:
                            st.error(f"批量删除API密钥失败: {str(e)}")

                    else:
                        st.warning("请输入至少一个API密钥进行删除。")
                elif delete_type == "续费码":
                    url = f"{API_CLAUDE35_URL}/renewal/delete"
                    payload = {"renewal_codes": api_keys_list}
                    response = requests.delete(url, json=payload)
                    st.write(response.json())
                else:
                    st.warning("请选择正确的删除类型。")

        elif api_key_function == "获取所有API密钥":
            st.subheader("获取所有API密钥")

            if st.button("获取所有API密钥"):
                url = f"{API_KEY_ROUTER}/list_keys"
                headers = {"accept": "application/json"}
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    api_keys = response.json()
                    st.write(api_keys)
                else:
                    st.error("获取API密钥列表失败。")

        elif api_key_function == "查看API密钥使用情况":
            data = get_api_stats()
            if data:
                df = create_dataframe(data)

                # 先展示统计指标
                col_metrics1, col_metrics2 = st.columns(2)
                with col_metrics1:
                    active_count = df["current_active"].value_counts().get(True, 0)
                    st.metric("当前活跃API Key数", active_count)
                with col_metrics2:
                    inactive_count = df["current_active"].value_counts().get(False, 0)
                    st.metric("当前不活跃API Key数", inactive_count)

                # 可视化部分
                st.subheader("使用量Top 10可视化")
                top_10_df = df.nlargest(10, "total_usage")

                chart = (
                    alt.Chart(top_10_df)
                    .mark_bar()
                    .encode(
                        x=alt.X(
                            "token:N",
                            sort="-y",
                            title="API Key",
                            axis=alt.Axis(labelAngle=-45),
                        ),
                        y=alt.Y("total_usage:Q", title="总使用量"),
                        tooltip=["token", "total_usage", "current_active"],
                        color=alt.condition(
                            alt.datum.current_active,
                            alt.value("#1f77b4"),  # 活跃状态颜色
                            alt.value("#d3d3d3"),  # 非活跃状态颜色
                        ),
                    )
                    .properties(height=400)
                )

                st.altair_chart(chart, use_container_width=True)

                # 查询部分
                with st.expander("查询特定 API Key", expanded=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        search_token = st.text_input("输入 API Key", key="search_input")
                    with col2:
                        search_button = st.button("查询", use_container_width=True)

                    if search_button and search_token:
                        filtered_df = df[
                            df["token"].str.contains(search_token, case=False)
                        ]
                        if not filtered_df.empty:
                            st.dataframe(filtered_df, use_container_width=True)
                        else:
                            st.warning("未找到匹配的 API Key")

                # 排序和数据显示部分
                with st.expander("数据排序与展示", expanded=True):
                    col3, col4, col5 = st.columns([2, 1, 1])

                    with col3:
                        sort_by = st.selectbox(
                            "选择排序字段",
                            [
                                "total_usage",
                                "last_3_hours",
                                "last_12_hours",
                                "last_24_hours",
                                "last_week",
                            ],
                        )
                    with col4:
                        sort_order = st.radio("排序方式", ["降序", "升序"])
                    with col5:
                        top_n = st.number_input(
                            "显示记录数", min_value=5, max_value=5000, value=10
                        )

                    ascending = sort_order == "升序"
                    sorted_df = df.sort_values(by=sort_by, ascending=ascending)
                    st.dataframe(sorted_df.head(top_n), use_container_width=True)

        elif api_key_function == "查看API设备使用情况":
            st.subheader("设备管理系统")

            # 初始化 session_state
            if "data" not in st.session_state:
                data = get_all_devices()
                if not data:
                    st.error("获取数据失败")
                    return
                initialize_session_state(data)
            else:
                data = st.session_state["data"]

            st.header("设备分布情况")
            col1, col2 = st.columns(2)
            device_stats = {}
            total_devices = 0
            for item in data["data"]:
                total_devices += len(item["devices"])
                for device in item["devices"]:
                    device_type = get_device_type(device["user_agent"])
                    device_stats[device_type] = device_stats.get(device_type, 0) + 1

            with col1:
                fig_pie = px.pie(
                    values=list(device_stats.values()),
                    names=list(device_stats.keys()),
                    title=f"设备类型分布 (总计: {total_devices}台设备)",
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            # Device Usage Histogram
            with col2:
                device_counts_per_user = [len(item["devices"]) for item in data["data"]]
                fig_hist = px.histogram(
                    device_counts_per_user,
                    nbins=20,
                    title="用户设备使用数量分布",
                    labels={"value": "设备数量", "count": "用户数"},
                    color_discrete_sequence=["#636EFA"],
                )
                fig_hist.update_layout(xaxis_title="设备数量", yaxis_title="用户数")
                st.plotly_chart(fig_hist, use_container_width=True)

            # 使用表单来包含输入框和按钮
            with st.form(key="search_form"):
                search_token = st.text_input(
                    "输入Token进行查询", value=st.session_state["search_token"]
                )
                submit_button = st.form_submit_button(label="查询")

            if submit_button:
                st.session_state["search_token"] = search_token.strip()

            if st.session_state["search_token"]:
                found = False
                for item in st.session_state["data"]["data"]:
                    if st.session_state["search_token"] in item["token"]:
                        found = True
                        st.subheader(f"Token: {item['token']}")

                        # Count devices by type
                        token_device_counts = {}
                        for device in item["devices"]:
                            device_type = get_device_type(device["user_agent"])
                            token_device_counts[device_type] = (
                                token_device_counts.get(device_type, 0) + 1
                            )

                        # Display device counts
                        cols = st.columns(len(token_device_counts))
                        for idx, (device_type, count) in enumerate(
                            token_device_counts.items()
                        ):
                            with cols[idx]:
                                st.metric(device_type, count)

                        # Display devices with logout buttons
                        st.subheader("设备列表")
                        devices_to_remove = []
                        for idx, device in enumerate(item["devices"]):
                            cols = st.columns([3, 1])
                            with cols[0]:
                                st.text(
                                    f"{get_device_type(device['user_agent'])} - {device['host']}"
                                )
                            with cols[1]:
                                button_key = f"logout_{item['token']}_{idx}"
                                if st.button("注销", key=button_key):
                                    result = logout_device(
                                        item["token"], device["user_agent"]
                                    )
                                    if result:
                                        st.success("注销成功")
                                        # 记录需要移除的设备
                                        devices_to_remove.append(idx)
                                    else:
                                        # error_message = result.get('error', '未知错误') if result else '请求失败'
                                        st.error(f"注销失败: {result}")

                        # 移除已注销的设备
                        if devices_to_remove:
                            # 移除设备时从后往前移除以避免索引问题
                            for idx in sorted(devices_to_remove, reverse=True):
                                del item["devices"][idx]
                            # 更新 session_state 数据
                            st.session_state["data"] = st.session_state["data"]

                if not found:
                    st.warning("未找到匹配的Token")

            st.header("所有Token设备统计")
            token_stats = []
            for item in st.session_state["data"]["data"]:
                token_device_counts = {}
                for device in item["devices"]:
                    device_type = get_device_type(device["user_agent"])
                    token_device_counts[device_type] = (
                        token_device_counts.get(device_type, 0) + 1
                    )

                token_stats.append(
                    {
                        "Token": item["token"],
                        "总设备数": len(item["devices"]),
                        **token_device_counts,
                    }
                )

            df_all = pd.DataFrame(token_stats)
            st.dataframe(df_all, use_container_width=True)


if check_password():
    main()
