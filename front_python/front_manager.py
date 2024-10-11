import json
from datetime import datetime, timedelta, time

import streamlit as st
import requests
import pandas as pd
import altair as alt
from tqdm import tqdm
from urllib.request import urlopen
import os

# running: BASE_URL="http://101.132.169.133:1145" streamlit run front_python/front_manager.py --server.port 5000

import requests
import json
from typing import List
import os
import time
from loguru import logger
from datetime import datetime
import pytz


def set_cn_time_zone():
    """设置当前进程的时区为中国时区"""
    os.environ["TZ"] = "Asia/Shanghai"
    try:
        time.tzset()
        logger.info("Set time zone to Asia/Shanghai.")
    except Exception as e:
        logger.error(f"Failed to set time zone: {e}")

set_cn_time_zone()


def get_user_tokens() -> List[dict]:
    url = "https://claude35.liuli.585dg.com/adminapi/chatgpt/user/list/"

    payload = json.dumps({})
    headers = {
        'APIAUTH': 'cccld',
        'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        return response.json()['data']
    else:
        raise Exception(f"Failed to fetch user tokens. Status code: {response.status_code}")


def delete_sessions(ids: List[int]):
    url = "https://claude35.liuli.585dg.com/adminapi/chatgpt/user/delete"

    payload = json.dumps({"ids": ids})
    headers = {
        'APIAUTH': 'cccld',
        'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code != 200:
        raise Exception(f"Failed to delete sessions. Status code: {response.status_code}")


def delete_batch_user_tokens(user_tokens: List[str], batch_size: int = 50):
    # Get all user data
    all_users = get_user_tokens()

    # Create a mapping of user tokens to their IDs
    token_to_id = {user['userToken']: user['id'] for user in all_users}

    # Find IDs for the given user tokens
    ids_to_delete = [token_to_id[token] for token in user_tokens if token in token_to_id]

    # Delete in batches
    for i in range(0, len(ids_to_delete), batch_size):
        batch = ids_to_delete[i:i + batch_size]
        delete_sessions(batch)
        print(f"Deleted batch of {len(batch)} sessions")

    message = f"Deleted a total of {len(ids_to_delete)} sessions"
    return message



def get_public_ip():
    try:
        response = urlopen("https://api.ipify.org")
        return response.read().decode("utf-8")
    except:
        return None


# class CookieUsageType(Enum):
#     WEB_LOGIN_ONLY = 0
#     REVERSE_API_ONLY = 1
#     BOTH = 2
usage_type_map = {0: "只用于网页登录", 1: "只用于官网1:1登录", 2: "都用"}


def get_type_color(client_type):
    return "#FF69B4" if client_type == "plus" else "#90EE90"


def get_usage_icon(usage_type):
    if usage_type == 0:
        return "🌐"  # Globe for web login
    elif usage_type == 1:
        return "🔒"  # Lock for official 1:1 login
    else:
        return "🔁"  # Recycle for both


def display_client_box(client):
    type_color = get_type_color(client["type"])
    # usage_icon = get_usage_icon(client['usage_type'])

    with st.container():
        client_container = st.empty()

        def update_client_display():
            client_container.markdown(
                f"""
            <div style="border:1px solid #ddd; padding:10px; margin:10px 0; border-radius:5px; background-color: #f0f8ff;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0;">{client['account']}</h3>
                    <span style="background-color: {type_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">{client['type']}</span>
                </div>
                <p style="margin: 5px 0;">使用类型: {get_usage_icon(client['usage_type'])} {usage_type_map[client['usage_type']]}</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

        update_client_display()

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button(
                "🌐 只用于网页登录",
                key=f"normal_{client['cookie_key']}",
                help="点击设置为只用于网页登录",
            ):
                if update_usage_type(client, 0):
                    update_client_display()
        with col2:
            if st.button(
                "🔒 只用于官网1:1登录",
                key=f"official_{client['cookie_key']}",
                help="点击设置为只用于官网1:1登录",
            ):
                if update_usage_type(client, 1):
                    update_client_display()
        with col3:
            if st.button(
                "🔁 都使用",
                key=f"both_{client['cookie_key']}",
                help="点击设置为两种登录都使用",
            ):
                if update_usage_type(client, 2):
                    update_client_display()

        # Display message for this client
        if client["cookie_key"] in st.session_state.messages:
            message, message_type = st.session_state.messages[client["cookie_key"]]
            display_message(message, message_type)


def update_all_usage_types(usage_type):
    success_count = 0
    total_count = sum(
        len(st.session_state.clients[client_type])
        for client_type in ["plus_clients", "basic_clients"]
    )

    progress_bar = st.progress(0)
    status_text = st.empty()

    for client_type in ["plus_clients", "basic_clients"]:
        for i, client in enumerate(st.session_state.clients[client_type]):
            if update_usage_type(client, usage_type):
                success_count += 1

            # 更新进度条和状态文本
            progress = (i + 1) / total_count
            progress_bar.progress(progress)
            status_text.text(f"正在更新... {i + 1}/{total_count}")

    status_text.text(f"更新完成: 成功 {success_count}/{total_count}")
    return success_count == total_count


def update_usage_type(client, usage_type):
    url = f"{BASE_URL}/api/v1/cookie/set_cookie_usage_type/{client['cookie_key']}"
    try:
        response = requests.put(url, params={"usage_type": usage_type})
        if response.status_code == 200:
            result = response.json()
            st.session_state.messages[client["cookie_key"]] = (
                f"成功更新：{result['message']}",
                "success",
            )
            # 更新本地客户数据
            client["usage_type"] = usage_type
            return True
        else:
            st.session_state.messages[client["cookie_key"]] = (
                f"更新失败：HTTP {response.status_code}",
                "error",
            )
    except requests.RequestException as e:
        st.session_state.messages[client["cookie_key"]] = (
            f"请求错误：{str(e)}",
            "error",
        )
    return False


def display_message(message, type="info"):
    if type == "success":
        st.success(message)
    elif type == "error":
        st.error(message)
    else:
        st.info(message)

import time



# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = {}


# claude3.ucas.life
BASE_URL = os.environ.get("BASE_URL", f"http://54.254.143.80:1145")

API_KEY_ROUTER = f"{BASE_URL}/api/v1/api_key"

# 设置页面标题
st.set_page_config(page_title="API密钥和Cookie管理")


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
            "验证API密钥",
            "删除API密钥",
            "批量删除API密钥",  # 新增这一行
            "获取所有API密钥",
            "重置API密钥使用量",  # Add this line
            "延长API密钥过期时间",  # 新增这一行
        ],
    )

    if api_key_function == "创建API密钥":
        st.subheader("创建API密钥")
        expiration_days = st.number_input("过期天数", min_value=0, value=0, step=1)
        expiration_hours = st.number_input("过期小时数", min_value=1, value=1, step=1)
        key_type = st.text_input("密钥类型", value="plus")
        key_number = st.number_input("密钥数量", min_value=1, value=1, step=1)
        # 定义选项
        options = [
            "🔒 只适用于官网镜像",
            "🌐 只适用于逆向网站",
            "🔁 全部设为都使用"
        ]

        # 创建选择框
        selected_option = st.selectbox("选择使用类型", options)
        total_hours = expiration_days * 24 + expiration_hours
        expiration_days_float = total_hours / 24
        if st.button("创建API密钥"):
            # url = f"{BASE_URL}/api/v1/api_key/create_key"
            url = f"{API_KEY_ROUTER}/create_key"
            payload = {
                "expiration_days": expiration_days_float,
                "key_type": key_type,
                "key_number": key_number,
            }
            response = requests.post(url, json=payload)

            # 然后还要添加新的
            new_payload = {
            }
            url = "https://claude35.liuli.585dg.com/adminapi/chatgpt/user/add"
            # 添加新用户API密钥

            api_keys = response.json().get("api_key")
            expire_date = datetime.now() + timedelta(hours=total_hours)
            expire_time = expire_date.strftime("%Y-%m-%d %H:%M:%S")
            is_plus = 1 if key_type == "plus" else 0

            progress_bar = st.progress(0)
            status = st.empty()

            # 获取API密钥的总数
            total_keys = len(api_keys)

            for index, api_key in enumerate(api_keys, start=1):
                # 更新进度条
                progress = int(index / total_keys * 100)
                progress_bar.progress(progress)

                # 更新状态信息
                status.text(f"正在处理 API 密钥 {index}/{total_keys}: {api_key}")

                # 添加新用户API密钥
                new_payload = {
                    "userToken": api_key,
                    "expireTime": expire_time,
                    "isPlus": is_plus
                }
                new_headers = {
                    'APIAUTH': 'cccld',
                    'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
                    'Content-Type': 'application/json'
                }
                # if selected_option != options[0]:
                if True:
                    new_response = requests.post(url, json=new_payload, headers=new_headers)
                    logger.debug(new_response)
                    if new_response.status_code == 200:
                        # st.success(f"API密钥 {api_key} 添加到Claude35成功!")
                        pass
                    else:
                        st.error(f"API密钥 {api_key} 添加到Claude35失败。")




            if response.status_code == 200:
                # st.success(json.dump(response.json(), indent=4))
                formatted_json = json.dumps(response.json(), indent=4, ensure_ascii=False)
                st.success("API密钥创建成功。")
                st.code(formatted_json, language="json")
            else:
                st.error("API密钥创建失败。")

            # 如果选择不是"只适用于官网镜像"，则删除所有生成的密钥
            if selected_option == options[1]:
                delete_url = f"{API_KEY_ROUTER}/delete_batch_keys"
                delete_payload = {"api_keys": api_keys}
                delete_response = requests.delete(delete_url, json=delete_payload)


    elif api_key_function == "验证API密钥":
        st.subheader("验证API密钥")
        api_key = st.text_input("API密钥")

        if st.button("验证API密钥"):
            # url = f"{BASE_URL}/api/v1/api_key/validate_key/{api_key}"
            url = f"{API_KEY_ROUTER}/validate_key/{api_key}"
            response = requests.get(url)
            if response.status_code == 200:
                st.success("API密钥有效。")
            else:
                st.error("API密钥无效。")

    elif api_key_function == "删除API密钥":
        st.subheader("删除API密钥")
        api_key_to_delete = st.text_input("要删除的API密钥")

        if st.button("删除API密钥"):
            # url = f"{BASE_URL}/api/v1/api_key/delete_key/{api_key_to_delete}"
            url = f"{API_KEY_ROUTER}/delete_key/{api_key_to_delete}"
            response = requests.delete(url)
            if response.status_code == 200:
                st.success("API密钥删除成功!")
            else:
                st.error("API密钥删除失败。")

    elif api_key_function == "批量删除API密钥":
        st.subheader("批量删除API密钥")
        api_keys_to_delete = st.text_area("输入要删除的API密钥（每行一个或用逗号分隔）")

        if st.button("批量删除API密钥"):
            # 先按换行符分割，然后对每个部分按逗号分割，最后去除空白
            api_keys_to_delete = api_keys_to_delete.replace('"', "")
            api_keys_to_delete = api_keys_to_delete.replace("'", "")
            api_keys_list = [
                key.strip()
                for line in api_keys_to_delete.split("\n")
                for key in line.split(",")
                if key.strip()
            ]

            if api_keys_list:
                try:
                    message = delete_batch_user_tokens(api_keys_list)
                    st.success(message)
                except Exception as e:
                    st.error(f"批量删除API密钥失败: {str(e)}")

                    #     # url = f"{BASE_URL}/api/v1/api_key/delete_batch_keys"
                    #     url = f"{API_KEY_ROUTER}/delete_batch_keys"
                    #     headers = {"Content-Type": "application/json"}
                    #     data = {"api_keys": api_keys_list}
                    #
                    #     response = requests.delete(url, headers=headers, json=data)
                    #
                    #     if response.status_code == 200:
                    #         st.success(f"成功删除 {len(api_keys_list)} 个API密钥。")
                    #         st.write(response.json())
                    #     else:
                    #         st.error("批量删除API密钥失败。")
                    #         st.write(response.text)

            else:
                    st.warning("请输入至少一个API密钥进行删除。")

    elif api_key_function == "获取所有API密钥":
        st.subheader("获取所有API密钥")

        if st.button("获取所有API密钥"):
            # url = f"{BASE_URL}/api/v1/api_key/list_keys"
            url = f"{API_KEY_ROUTER}/list_keys"
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                api_keys = response.json()
                st.write(api_keys)
            else:
                st.error("获取API密钥列表失败。")

    elif api_key_function == "查看API密钥使用情况":

        st.subheader("绘制API密钥使用情况条状图")
        key_type = st.selectbox("请输入要查看的API密钥类型", ["plus", "basic"])
        top_n = st.number_input(
            "请输入要显示的前几个API密钥", min_value=1, value=5, step=1
        )

        if st.button("绘制API密钥使用情况条状图"):
            # url = f"{BASE_URL}/api/v1/api_key/list_keys"
            url = f"{API_KEY_ROUTER}/list_keys"
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                api_keys = response.json()
                api_key_usage = []

                for api_key, info in tqdm(api_keys.items()):
                    try:
                        type = info["key_type"]
                        if type == key_type:
                            api_key_usage.append(
                                {"api_key": api_key, "usage": info["usage"]}
                            )
                    except Exception as e:
                        pass

                api_key_usage_df = pd.DataFrame(api_key_usage)

                api_key_usage_df = api_key_usage_df.sort_values(
                    "usage", ascending=False
                ).head(top_n)
                chart = (
                    alt.Chart(api_key_usage_df)
                    .mark_bar()
                    .encode(
                        x=alt.X("api_key:N", title="API密钥"),
                        y=alt.Y("usage:Q", title="使用量"),
                        tooltip=["api_key", "usage"],
                    )
                    .properties(
                        title=f"Top {top_n} API密钥使用情况",
                    )
                )
                st.altair_chart(chart, use_container_width=True)
                st.write(api_key_usage_df)
            else:
                st.error("获取API密钥列表失败。")

                st.subheader("查看API密钥使用情况")
        api_key = st.text_input("请输入要查看的API密钥")

        if st.button("查看API密钥使用情况"):
            # url = f"{BASE_URL}/api/v1/api_key/get_information/{api_key}"
            url = f"{API_KEY_ROUTER}/get_information/{api_key}"
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                api_key_info = response.json()
                st.write(api_key_info)
            else:
                st.error("获取API密钥使用情况失败。")

    elif api_key_function == "重置API密钥使用量":
        st.subheader("重置API密钥使用量")
        api_key_to_reset = st.text_input("要重置的API密钥")

        if st.button("重置使用量"):
            # url = f"{BASE_URL}/api/v1/reset_current_usage/{api_key_to_reset}"
            url = f"{API_KEY_ROUTER}/reset_current_usage/{api_key_to_reset}"
            response = requests.post(url)
            if response.status_code == 200:
                result = response.json()
                st.success(f"API密钥 已重置： {result}")
            else:
                st.error("重置API密钥使用量失败。")

    elif api_key_function == "延长API密钥过期时间":
        st.subheader("延长API密钥过期时间")
        api_key_to_extend = st.text_input("要延长的API密钥")
        additional_days = st.number_input("要延长的天数", min_value=1, value=30, step=1)

        if st.button("延长过期时间"):
            # url = f"{BASE_URL}/api/v1/extend_expiration/{api_key_to_extend}"
            url = f"{API_KEY_ROUTER}/extend_expiration/{api_key_to_extend}"
            payload = {"additional_days": additional_days}
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                result = response.json()
                st.success(f"API密钥过期时间已延长：{result['message']}")
            else:
                st.error("延长API密钥过期时间失败。")
                st.write(response.text)


elif main_function == "Cookie管理":
    # Cookie管理部分
    cookie_function = st.sidebar.radio(
        "Cookie管理",
        [
            "上传Cookie",
            "删除Cookie",
            "刷新Cookie",
            "列出所有Cookie",
            "更新Cookie",
            "调整Cookie是否为官网1:1",
        ],
    )

    if cookie_function == "上传Cookie":
        st.subheader("上传Cookie")
        cookie = st.text_input("Cookie")
        cookie_type = st.selectbox("Cookie类型", ["basic", "plus", "test", "normal"])
        account = st.text_input("账号", value="")

        if st.button("上传Cookie"):
            url = f"{BASE_URL}/api/v1/cookie/upload_cookie"
            params = {"cookie": cookie, "cookie_type": cookie_type, "account": account}
            response = requests.post(url, params=params)
            if response.status_code == 200:
                st.success(response.json())
            else:
                st.error("Cookie上传失败。")

    elif cookie_function == "删除Cookie":
        st.subheader("删除Cookie")
        cookie_key_to_delete = st.text_input("要删除的Cookie Key")

        if st.button("删除Cookie"):
            url = f"{BASE_URL}/api/v1/cookie/delete_cookie/{cookie_key_to_delete}"
            response = requests.delete(url)
            if response.status_code == 200:
                st.success("Cookie删除成功!")
            else:
                st.error("Cookie删除失败。")

    elif cookie_function == "刷新Cookie":
        st.subheader("刷新Cookie")

        if st.button("刷新Cookie"):
            url = f"{BASE_URL}/api/v1/cookie/refresh_cookies"
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                st.success("Cookie刷新成功!")
            else:
                st.error("Cookie刷新失败。")

    elif cookie_function == "列出所有Cookie":
        st.subheader("列出所有Cookie")

        if st.button("列出所有Cookie"):
            url = f"{BASE_URL}/api/v1/cookie/list_all_cookies"
            response = requests.get(url)
            if response.status_code == 200:
                cookies = response.json()
                st.write(cookies)
            else:
                st.error("获取Cookie列表失败。")

    elif cookie_function == "更新Cookie":
        st.subheader("更新Cookie")
        cookie_key_to_update = st.text_input("要更新的Cookie Key")
        updated_cookie = st.text_input("更新后的Cookie")
        updated_account = st.text_input("更新后的账号", value="")

        if st.button("更新Cookie"):
            url = f"{BASE_URL}/api/v1/cookie/update_cookie/{cookie_key_to_update}"
            params = {"cookie": updated_cookie, "account": updated_account}
            response = requests.put(url, params=params)
            if response.status_code == 200:
                st.success("Cookie更新成功!")
            else:
                st.error("Cookie更新失败。")

    elif cookie_function == "调整Cookie是否为官网1:1":
        st.subheader("调整Cookie是否为官网1:1")
        # 方法2：使用 st.info
        st.markdown(
            """
         **使用说明：** 在下方列表中，您可以查看所有Cookie的当前状态，并通过点击按钮来更改它们的使用类型。
         更改将立即生效， 在状态栏中能看到对应的修改:
         - 网页登录: 仅用于网页登录, 也就是该账号只用于网页登录。
         - 官网1:1登录: 仅用于官网1:1登录, 也就是该账号只用于官网1:1登录。
         - 都使用: 两种登录都使用, 也就是该账号既可以用于网页登录，也可以用于官网1:1登录。（状态页面会有两个同样的账号）
         """
        )

        if st.button("刷新客户列表"):
            if st.session_state.clients:
                del st.session_state.clients
            st.experimental_rerun()

        # 添加一键设置所有Cookie使用类型的按钮
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🌐 全部设为只用于网页登录"):
                if update_all_usage_types(0):
                    st.success("所有Cookie已成功设置为只用于网页登录")
                st.experimental_rerun()
        with col2:
            if st.button("🔒 全部设为只用于官网1:1登录"):
                if update_all_usage_types(1):
                    st.success("所有Cookie已成功设置为只用于官网1:1登录")
                st.experimental_rerun()
        with col3:
            if st.button("🔁 全部设为都使用"):
                if update_all_usage_types(2):
                    st.success("所有Cookie已成功设置为都使用")
                st.experimental_rerun()

        url = f"{BASE_URL}/api/v1/cookie/clients_information"

        if "clients" not in st.session_state:
            response = requests.get(url)
            if response.status_code == 200:
                st.session_state.clients = response.json()["data"]
            else:
                display_message("获取Cookie状态列表失败。", "error")

        for client_type in ["plus_clients", "basic_clients"]:
            st.subheader(f"{'基础' if client_type == 'basic_clients' else 'Plus'} 客户")
            for client in st.session_state.clients[client_type]:
                display_client_box(client)
