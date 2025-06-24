import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta
from typing import Optional

import altair as alt
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from loguru import logger

from api_key_utils import build_client_headers, delete_batch_api_keys
from authen import check_password
from conversation_utils import get_all_conversations, get_single_conversation
from device_utils import get_all_devices, get_device_type, logout_device
from front_configs import *
from front_utils import (
    create_sorux_accounts,
    create_sorux_accounts_v2,
    create_sorux_redemption_codes,
    delete_sorux_accounts,
    parse_chatgpt_credentials,
)

# running:  streamlit run front_python/front_manager.py --server.port 5000

st.set_page_config(page_title="API密钥和Cookie管理")
logger.add(STREAMLIT_LOGS / "log_file.log", rotation="1 week")  # 每周轮换一次文件


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

    url = f"{CLAUDE_AUDIT_BASE_URL}/token_stats?usage_type={usage_type}"
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


def set_cn_time_zone():
    """设置当前进程的时区为中国时区"""
    import os

    os.environ["TZ"] = "Asia/Shanghai"
    try:
        import time

        if hasattr(time, "tzset"):
            time.tzset()
        logger.info("Set time zone to Asia/Shanghai.")
    except Exception as e:
        logger.error(f"Failed to set time zone: {e}")


# ============ 策略模式实现 ============


class PageHandler(ABC):
    """页面处理器抽象基类"""

    @abstractmethod
    def render(self):
        """渲染页面内容"""
        pass


class APIKeyCreationHandler(PageHandler):
    """API密钥创建处理器"""

    def render(self):
        st.subheader("创建API密钥")

        # 基本设置
        col1, col2 = st.columns(2)
        with col1:
            key_type = st.text_input("密钥类型", value="plus")
            key_number = st.number_input("密钥数量", min_value=1, value=1, step=1)
        with col2:
            expiration_days = st.number_input("过期天数", min_value=0, value=0, step=1)
            expiration_hours = st.number_input(
                "过期小时数(只有Claude支持小数)",
                min_value=0.1,
                value=1.0,
                step=1.0,
                format="%.1f",
            )

        # 速率限制设置
        st.markdown("### 速率限制")
        col3, col4 = st.columns(2)
        with col3:
            message_limited = st.number_input("消息速率限速条数", min_value=1, value=5, step=1)
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
            "🤖 适用于ChatGPT镜像-懒激活",
            "🔄 只用于claude账号池续费",
            "💰 创建ChatGPT兑换码",
        ]
        selected_option = st.selectbox("选择使用类型", options)

        if st.button("创建API密钥"):
            self._create_api_keys(
                key_type,
                key_number,
                expiration_days,
                expiration_hours,
                message_limited,
                rate_refresh_time,
                message_bucket_sum,
                message_bucket_time,
                selected_option,
            )

    def _create_api_keys(
        self,
        key_type,
        key_number,
        expiration_days,
        expiration_hours,
        message_limited,
        rate_refresh_time,
        message_bucket_sum,
        message_bucket_time,
        selected_option,
    ):
        """创建API密钥的具体实现"""
        total_hours = expiration_days * 24 + expiration_hours
        expiration_days_float = total_hours / 24

        api_keys = []
        sorux_accounts = []

        # 处理ChatGPT兑换码创建
        if selected_option == "💰 创建ChatGPT兑换码":
            points = expiration_days
            redemption_codes = asyncio.run(
                create_sorux_redemption_codes(points=points, code_number=key_number)
            )
            if redemption_codes:
                st.success("ChatGPT兑换码创建成功")
                codes_str = "\n".join(
                    [code["code"] for code in redemption_codes if code]
                )
                st.text_area("兑换码", codes_str)
                st.code(
                    json.dumps(redemption_codes, indent=4, ensure_ascii=False),
                    language="json",
                )

        # 处理续费码创建
        elif selected_option == "🔄 只用于claude账号池续费":
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
                renewal_codes_str = "\n".join(renewal_codes)
                st.text_area("续费码", renewal_codes_str)
                st.code(
                    json.dumps(
                        {"renewal_codes": renewal_codes}, indent=4, ensure_ascii=False
                    ),
                    language="json",
                )

        else:
            self._handle_regular_api_key_creation(
                selected_option,
                expiration_days_float,
                key_type,
                key_number,
                total_hours,
                message_limited,
                rate_refresh_time,
                message_bucket_sum,
                message_bucket_time,
                api_keys,
                sorux_accounts,
            )

    def _handle_regular_api_key_creation(
        self,
        selected_option,
        expiration_days_float,
        key_type,
        key_number,
        total_hours,
        message_limited,
        rate_refresh_time,
        message_bucket_sum,
        message_bucket_time,
        api_keys,
        sorux_accounts,
    ):
        """处理常规API密钥创建"""
        if selected_option in ["🔒 只适用于claude账号池镜像", "🔁 全部设为都使用"]:
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
        if selected_option in ["🤖 适用于ChatGPT镜像", "🔁 全部设为都使用"]:
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
        elif selected_option == "🤖 适用于ChatGPT镜像-懒激活":
            sorux_accounts = asyncio.run(
                create_sorux_accounts_v2(
                    key_number,
                    int(total_hours),
                    message_limited,
                    rate_refresh_time,
                    message_bucket_sum,
                    message_bucket_time,
                )
            )

        self._process_api_keys(api_keys, total_hours, key_type, selected_option)
        self._display_results(api_keys, sorux_accounts, selected_option)

    def _process_api_keys(self, api_keys, total_hours, key_type, selected_option):
        """处理API密钥"""
        if api_keys:
            total_hours += 8
            expire_date = datetime.now() + timedelta(hours=total_hours)
            expire_time = expire_date.strftime("%Y-%m-%d %H:%M:%S")
            is_plus = 1 if key_type == "plus" else 0

            progress_bar = st.progress(0)
            status = st.empty()

            total_keys = len(api_keys)
            for index, api_key in enumerate(api_keys, start=1):
                progress = int(index / total_keys * 100)
                progress_bar.progress(progress)
                status.text(f"正在处理 API 密钥 {index}/{total_keys}: {api_key}")

                if selected_option != "🌐 只适用于逆向网站":
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

        # Delete API keys if only reverse proxy is needed
        if selected_option == "🌐 只适用于逆向网站" and api_keys:
            delete_url = f"{API_KEY_ROUTER}/delete_batch_keys"
            delete_payload = {"api_keys": api_keys}
            delete_response = requests.delete(delete_url, json=delete_payload)

    def _display_results(self, api_keys, sorux_accounts, selected_option):
        """显示结果"""
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


class APIKeyUsageHandler(PageHandler):
    """API密钥使用情况处理器"""

    def render(self):
        data = get_api_stats()
        if data:
            df = create_dataframe(data)

            # 统计指标
            self._display_metrics(df)

            # 可视化
            self._display_visualization(df)

            # 查询功能
            self._display_search(df)

            # 排序和数据显示
            self._display_sorted_data(df)

    def _display_metrics(self, df):
        """显示统计指标"""
        col_metrics1, col_metrics2 = st.columns(2)
        with col_metrics1:
            active_count = df["current_active"].value_counts().get(True, 0)
            st.metric("当前活跃API Key数", active_count)
        with col_metrics2:
            inactive_count = df["current_active"].value_counts().get(False, 0)
            st.metric("当前不活跃API Key数", inactive_count)

    def _display_visualization(self, df):
        """显示可视化图表"""
        st.subheader("使用量Top 10可视化")
        top_10_df = df.nlargest(10, "total_usage")

        # 简化图表创建以避免类型错误
        try:
            # 使用 plotly 替代 altair 避免类型问题
            import plotly.express as px

            fig = px.bar(
                top_10_df,
                x="token",
                y="total_usage",
                title="使用量Top 10",
                labels={"token": "API Key", "total_usage": "总使用量"},
                height=400,
            )
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"图表渲染失败: {str(e)}")
            # 降级到简单的数据显示
            st.dataframe(top_10_df, use_container_width=True)

    def _display_search(self, df):
        """显示搜索功能"""
        with st.expander("查询特定 API Key", expanded=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                search_token = st.text_input("输入 API Key", key="search_input")
            with col2:
                search_button = st.button("查询", use_container_width=True)

            if search_button and search_token:
                filtered_df = df[df["token"].str.contains(search_token, case=False)]
                if not filtered_df.empty:
                    st.dataframe(filtered_df, use_container_width=True)
                else:
                    st.warning("未找到匹配的 API Key")

    def _display_sorted_data(self, df):
        """显示排序数据"""
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
                top_n = st.number_input("显示记录数", min_value=5, max_value=5000, value=10)

            ascending = sort_order == "升序"
            sorted_df = df.sort_values(by=sort_by, ascending=ascending)
            st.dataframe(sorted_df.head(top_n), use_container_width=True)


class APIKeyDeviceHandler(PageHandler):
    """API密钥设备管理处理器"""

    def render(self):
        st.subheader("设备管理系统")

        # 初始化 session_state
        if "data" not in st.session_state:
            data = get_all_devices()
            if not data:
                st.info(data)
                st.error("获取数据失败")
                return
            initialize_session_state(data)
        else:
            data = st.session_state["data"]

        # 设备分布情况
        self._display_device_distribution(data)

        # 搜索功能
        self._display_device_search()

        # 所有Token统计
        self._display_all_token_stats()

    def _display_device_distribution(self, data):
        """显示设备分布情况"""
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

    def _display_device_search(self):
        """显示设备搜索功能"""
        with st.form(key="search_form"):
            search_token = st.text_input(
                "输入Token进行查询", value=st.session_state.get("search_token", "")
            )
            submit_button = st.form_submit_button(label="查询")

        if submit_button:
            st.session_state["search_token"] = (
                search_token.strip() if search_token else ""
            )

        if st.session_state.get("search_token"):
            self._handle_token_search(st.session_state["search_token"])

    def _handle_token_search(self, search_token):
        """处理Token搜索"""
        found = False
        for item in st.session_state["data"]["data"]:
            if search_token in item["token"]:
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
                if token_device_counts:
                    cols = st.columns(len(token_device_counts))
                    for idx, (device_type, count) in enumerate(
                        token_device_counts.items()
                    ):
                        with cols[idx]:
                            st.metric(device_type, count)

                # Display devices with logout buttons
                st.subheader("设备列表")
                self._handle_device_logout(item)

        if not found:
            st.warning("未找到匹配的Token")

    def _handle_device_logout(self, item):
        """处理设备注销"""
        devices_to_remove = []
        for idx, device in enumerate(item["devices"]):
            cols = st.columns([3, 1])
            with cols[0]:
                st.text(f"{get_device_type(device['user_agent'])} - {device['host']}")
            with cols[1]:
                button_key = f"logout_{item['token']}_{idx}"
                if st.button("注销", key=button_key):
                    result = logout_device(item["token"], device["user_agent"])
                    if result:
                        st.success("注销成功")
                        devices_to_remove.append(idx)
                    else:
                        st.error(f"注销失败: {result}")

        # 移除已注销的设备
        if devices_to_remove:
            for idx in sorted(devices_to_remove, reverse=True):
                del item["devices"][idx]
            st.session_state["data"] = st.session_state["data"]

    def _display_all_token_stats(self):
        """显示所有Token统计"""
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


class APIKeyDeletionHandler(PageHandler):
    """API密钥删除处理器"""

    def render(self):
        st.subheader("批量删除API密钥")
        api_keys_to_delete = st.text_area("输入要删除的API密钥（每行一个或用逗号分隔）")
        delete_type = st.selectbox("选择删除类型", ["API密钥", "续费码", "ChatGPT账号"], index=0)

        # 清理输入数据
        api_keys_to_delete = api_keys_to_delete.replace('"', "").replace("'", "")

        api_keys_list = self._parse_delete_input(api_keys_to_delete, delete_type)

        if st.button("批量删除"):
            self._handle_deletion(delete_type, api_keys_list)

    def _parse_delete_input(self, input_text, delete_type):
        """解析删除输入"""
        if delete_type in ["API密钥", "续费码"]:
            return [
                key.strip()
                for line in input_text.split("\n")
                for key in line.split(",")
                if key.strip()
            ]
        else:  # ChatGPT账号
            return asyncio.run(parse_chatgpt_credentials(input_text))

    def _handle_deletion(self, delete_type, api_keys_list):
        """处理删除操作"""
        deletion_handlers = {
            "API密钥": self._delete_api_keys,
            "续费码": self._delete_renewal_codes,
            "ChatGPT账号": self._delete_chatgpt_accounts,
        }

        handler = deletion_handlers.get(delete_type)
        if handler:
            handler(api_keys_list)

    def _delete_api_keys(self, api_keys_list):
        """删除API密钥"""
        if api_keys_list:
            try:
                message = delete_batch_api_keys(api_keys_list)
                st.success(message)
            except Exception as e:
                st.error(f"批量删除API密钥失败: {str(e)}")
        else:
            st.warning("请输入至少一个API密钥进行删除。")

    def _delete_renewal_codes(self, renewal_codes_list):
        """删除续费码"""
        url = f"{API_CLAUDE35_URL}/renewal/delete"
        payload = {"renewal_codes": renewal_codes_list}
        response = requests.delete(url, json=payload)
        st.write(response.json())

    def _delete_chatgpt_accounts(self, accounts_list):
        """删除ChatGPT账号"""
        if accounts_list:
            try:
                res = asyncio.run(delete_sorux_accounts(accounts_list))
                st.info(res)
            except Exception as e:
                st.error(f"删除ChatGPT账号失败: {str(e)}")
        else:
            st.warning("请输入至少一个ChatGPT账号进行删除。")


class ConversationManagementHandler(PageHandler):
    """对话管理处理器"""

    def render(self):
        st.subheader("Claude镜像对话管理")

        # Create tabs for different query types
        tab1, tab2 = st.tabs(["单一用户查询", "所有用户查询"])

        with tab1:
            self._render_single_user_query()

        with tab2:
            self._render_all_users_query()

    def _render_single_user_query(self):
        """渲染单一用户查询"""
        st.subheader("单一用户查询")
        api_key = st.text_input("输入API Key")
        conversation_id = st.text_input("输入对话ID (可选)")

        if st.button("查询单一用户对话"):
            if api_key:
                conv_id = (
                    conversation_id
                    if conversation_id and conversation_id.strip()
                    else None
                )
                result = asyncio.run(get_single_conversation(api_key, conv_id))
                if result:
                    st.success("查询成功")
                    self._display_download_buttons(result, "conversation")
                else:
                    st.error("未找到对话记录")
            else:
                st.warning("请输入API Key")

    def _render_all_users_query(self):
        """渲染所有用户查询"""
        st.subheader("所有用户查询")
        time_filter = st.selectbox(
            "选择时间范围",
            ["one_day", "three_days", "one_week", "one_month", "all"],
            format_func=lambda x: {
                "one_day": "一天内",
                "three_days": "三天内",
                "one_week": "一周内",
                "one_month": "一个月内",
                "all": "全部",
            }[x],
        )

        if st.button("查询所有用户对话"):
            result = asyncio.run(get_all_conversations(time_filter))
            if result:
                st.success("查询成功")
                self._display_download_buttons(
                    result, f"all_conversations_{time_filter}"
                )
            else:
                st.error("未找到对话记录")

    def _display_download_buttons(self, result, filename_prefix):
        """显示下载按钮"""
        col1, col2 = st.columns(2)
        with col1:
            # JSON download
            json_str = json.dumps(result, ensure_ascii=False, indent=2)
            st.download_button(
                label="下载JSON格式",
                data=json_str,
                file_name=f"{filename_prefix}.json",
                mime="application/json",
            )
        with col2:
            # Text download
            text_str = "暂未适配文本格式"
            st.download_button(
                label="下载文本格式",
                data=text_str,
                file_name=f"{filename_prefix}.txt",
                mime="text/plain",
            )


class ClaudeRenewalCodeManagementHandler(PageHandler):
    """Claude续费码管理处理器"""

    def render(self):
        st.subheader("Claude镜像续费码管理")

        # Create tabs for different query types
        tab1, tab2, tab3 = st.tabs(["所有续费码", "单个续费码查询", "续费码统计"])

        with tab1:
            self._render_all_renewal_codes()

        with tab2:
            self._render_single_renewal_code_query()

        with tab3:
            self._render_renewal_code_statistics()

    def _render_all_renewal_codes(self):
        """渲染所有续费码"""
        st.subheader("所有续费码列表")

        # 添加筛选选项
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox(
                "状态筛选",
                ["全部", "未使用", "已使用"],
                format_func=lambda x: {"全部": "all", "未使用": "unused", "已使用": "used"}.get(
                    x, x
                ),
            )
        with col2:
            limit = st.number_input(
                "显示数量", min_value=10, max_value=10000, value=50, step=10
            )
        with col3:
            if st.button("刷新数据", use_container_width=True):
                st.rerun()

        if st.button("获取所有续费码"):
            try:
                url = f"{API_CLAUDE35_URL}/renewal/all"
                response = requests.get(url)

                if response.status_code == 200:
                    data = response.json()
                    total = data.get("total", 0)
                    codes = data.get("codes", [])

                    st.success(f"获取成功，共 {total} 个续费码")

                    # 数据筛选
                    if status_filter != "全部":
                        filter_status = {"未使用": "unused", "已使用": "used"}[status_filter]
                        codes = [
                            code for code in codes if code["status"] == filter_status
                        ]

                    # 限制显示数量
                    codes = codes[:limit]

                    if codes:
                        # 转换为DataFrame便于显示
                        df_data = []
                        for code in codes:
                            df_data.append(
                                {
                                    "续费码": code["code"],
                                    "状态": "已使用" if code["status"] == "used" else "未使用",
                                    "时长": f"{code['days']}天{code['hours']}小时{code['minutes']}分钟",
                                    "总分钟数": code["total_minutes"],
                                    "创建时间": code["created_at"][:19].replace("T", " "),
                                    "使用时间": code.get("used_at", "")[:19].replace(
                                        "T", " "
                                    )
                                    if code.get("used_at")
                                    else "",
                                    "使用者": code.get("used_by", ""),
                                }
                            )

                        df = pd.DataFrame(df_data)

                        # 显示筛选后的统计
                        col_stat1, col_stat2 = st.columns(2)
                        with col_stat1:
                            used_count = len(
                                [c for c in codes if c["status"] == "used"]
                            )
                            st.metric("已使用", used_count)
                        with col_stat2:
                            unused_count = len(
                                [c for c in codes if c["status"] == "unused"]
                            )
                            st.metric("未使用", unused_count)

                        # 显示数据表格
                        st.dataframe(df, use_container_width=True)

                        # 下载功能
                        self._display_download_buttons_for_codes(
                            codes, f"renewal_codes_{status_filter}"
                        )
                    else:
                        st.info("没有符合条件的续费码")

                else:
                    st.error(f"请求失败，状态码: {response.status_code}")

            except Exception as e:
                st.error(f"获取续费码失败: {str(e)}")

    def _render_single_renewal_code_query(self):
        """渲染单个续费码查询"""
        st.subheader("单个续费码查询")

        renewal_code = st.text_input("输入续费码", placeholder="例如: rnw-20_1_0-0624-22e638")

        if st.button("查询续费码"):
            if renewal_code.strip():
                try:
                    url = f"{API_CLAUDE35_URL}/renewal/info/{renewal_code.strip()}"
                    response = requests.get(url)

                    if response.status_code == 200:
                        data = response.json()
                        st.success("查询成功")

                        # 显示详细信息
                        col1, col2 = st.columns(2)

                        with col1:
                            st.metric("续费码", data["code"])
                            st.metric(
                                "状态", "已使用" if data["status"] == "used" else "未使用"
                            )
                            st.metric(
                                "总时长",
                                f"{data['days']}天{data['hours']}小时{data['minutes']}分钟",
                            )

                        with col2:
                            st.metric("总分钟数", data["total_minutes"])
                            st.metric("创建时间", data["created_at"][:19].replace("T", " "))
                            if data.get("used_at"):
                                st.metric(
                                    "使用时间", data["used_at"][:19].replace("T", " ")
                                )
                            if data.get("used_by"):
                                st.metric("使用者", data["used_by"])

                        # 显示原始JSON数据
                        with st.expander("原始数据", expanded=False):
                            st.json(data)

                    elif response.status_code == 404:
                        st.error("续费码不存在")
                    else:
                        st.error(f"查询失败，状态码: {response.status_code}")

                except Exception as e:
                    st.error(f"查询续费码失败: {str(e)}")
            else:
                st.warning("请输入续费码")

    def _render_renewal_code_statistics(self):
        """渲染续费码统计"""
        st.subheader("续费码统计")

        if st.button("获取统计数据"):
            try:
                url = f"{API_CLAUDE35_URL}/renewal/all"
                response = requests.get(url)

                if response.status_code == 200:
                    data = response.json()
                    codes = data.get("codes", [])

                    if codes:
                        # 基本统计
                        total = len(codes)
                        used_count = len([c for c in codes if c["status"] == "used"])
                        unused_count = len(
                            [c for c in codes if c["status"] == "unused"]
                        )

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("总数", total)
                        with col2:
                            st.metric("已使用", used_count)
                        with col3:
                            st.metric("未使用", unused_count)

                        # 使用率饼图
                        st.subheader("使用状态分布")
                        import plotly.express as px

                        status_data = pd.DataFrame(
                            {"状态": ["已使用", "未使用"], "数量": [used_count, unused_count]}
                        )

                        fig_pie = px.pie(
                            status_data, values="数量", names="状态", title="续费码使用状态分布"
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)

                        # 时长分布统计
                        st.subheader("时长分布")
                        duration_stats = {}
                        for code in codes:
                            duration_key = f"{code['days']}天{code['hours']}小时"
                            duration_stats[duration_key] = (
                                duration_stats.get(duration_key, 0) + 1
                            )

                        if duration_stats:
                            duration_data = [
                                {"时长": k, "数量": v} for k, v in duration_stats.items()
                            ]
                            duration_df = pd.DataFrame(duration_data)

                            fig_bar = px.bar(
                                duration_df, x="时长", y="数量", title="续费码时长分布"
                            )
                            fig_bar.update_xaxes(tickangle=-45)
                            st.plotly_chart(fig_bar, use_container_width=True)

                        # 创建时间趋势（按日期分组）
                        st.subheader("创建时间趋势")
                        date_stats = {}
                        for code in codes:
                            date = code["created_at"][:10]  # 取日期部分
                            date_stats[date] = date_stats.get(date, 0) + 1

                        if date_stats:
                            date_data = [
                                {"日期": k, "数量": v} for k, v in date_stats.items()
                            ]
                            date_df = pd.DataFrame(date_data)
                            date_df = date_df.sort_values("日期")

                            fig_line = px.line(
                                date_df, x="日期", y="数量", title="续费码每日创建数量趋势"
                            )
                            fig_line.update_xaxes(tickangle=-45)
                            st.plotly_chart(fig_line, use_container_width=True)

                    else:
                        st.info("没有续费码数据")

                else:
                    st.error(f"获取数据失败，状态码: {response.status_code}")

            except Exception as e:
                st.error(f"获取统计数据失败: {str(e)}")

    def _display_download_buttons_for_codes(self, codes, filename_prefix):
        """显示续费码下载按钮"""
        col1, col2, col3 = st.columns(3)

        with col1:
            # JSON下载
            json_str = json.dumps(codes, ensure_ascii=False, indent=2)
            st.download_button(
                label="下载JSON格式",
                data=json_str,
                file_name=f"{filename_prefix}.json",
                mime="application/json",
            )

        with col2:
            # CSV下载
            df_data = []
            for code in codes:
                df_data.append(
                    {
                        "续费码": code["code"],
                        "状态": code["status"],
                        "天数": code["days"],
                        "小时": code["hours"],
                        "分钟": code["minutes"],
                        "总分钟数": code["total_minutes"],
                        "创建时间": code["created_at"],
                        "使用时间": code.get("used_at", ""),
                        "使用者": code.get("used_by", ""),
                    }
                )

            df = pd.DataFrame(df_data)
            csv_str = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="下载CSV格式",
                data=csv_str,
                file_name=f"{filename_prefix}.csv",
                mime="text/csv",
            )

        with col3:
            # 纯续费码列表下载
            code_list = "\n".join([code["code"] for code in codes])
            st.download_button(
                label="下载纯续费码",
                data=code_list,
                file_name=f"{filename_prefix}_codes_only.txt",
                mime="text/plain",
            )


# ============ 工厂模式实现 ============


class PageHandlerFactory:
    """页面处理器工厂"""

    @staticmethod
    def create_handler(main_function: str, sub_function: str) -> PageHandler:
        """根据功能选择创建相应的处理器"""

        if main_function == "API密钥管理":
            api_handlers = {
                "创建API密钥": APIKeyCreationHandler,
                "查看API密钥使用情况": APIKeyUsageHandler,
                "查看API设备使用情况": APIKeyDeviceHandler,
                "批量删除API密钥": APIKeyDeletionHandler,
            }
            handler_class = api_handlers.get(sub_function)

        elif main_function == "对话管理":
            conversation_handlers = {
                "Claude镜像对话管理": ConversationManagementHandler,
            }
            handler_class = conversation_handlers.get(sub_function)

        elif main_function == "续费码管理":
            renewal_code_handlers = {
                "Claude镜像续费码管理": ClaudeRenewalCodeManagementHandler,
                # "ChatGPT账号续费码管理": ChatGPTRenewalCodeManagementHandler,
            }
            handler_class = renewal_code_handlers.get(sub_function)

        else:
            handler_class = None

        if handler_class:
            return handler_class()
        else:
            raise ValueError(f"未知的功能组合: {main_function} -> {sub_function}")


# ============ 主函数重构 ============


def main():
    """重构后的主函数 - 使用策略模式和工厂模式"""
    set_cn_time_zone()

    # 设置页面标题
    st.title("API密钥和Cookie管理")

    # 在左侧边栏添加主要功能选择
    main_function = st.sidebar.radio("主要功能", ["API密钥管理", "对话管理", "续费码管理"])

    try:
        if main_function == "API密钥管理":
            # API密钥管理部分
            api_key_function = st.sidebar.radio(
                "API密钥管理",
                [
                    "创建API密钥",
                    "查看API密钥使用情况",
                    "查看API设备使用情况",
                    "批量删除API密钥",
                ],
            )

            # 使用工厂模式创建处理器
            handler = PageHandlerFactory.create_handler(main_function, api_key_function)
            handler.render()

        elif main_function == "对话管理":
            # 对话管理部分
            conversation_function = st.sidebar.radio("对话管理", ["Claude镜像对话管理"])

            # 使用工厂模式创建处理器
            handler = PageHandlerFactory.create_handler(
                main_function, conversation_function
            )
            handler.render()

        elif main_function == "续费码管理":
            # 续费码管理部分
            renewal_code_function = st.sidebar.radio(
                "续费码管理", ["Claude镜像续费码管理"]
            )  # , "ChatGPT账号续费码管理"])

            # 使用工厂模式创建处理器
            handler = PageHandlerFactory.create_handler(
                main_function, renewal_code_function
            )
            handler.render()

    except ValueError as e:
        st.error(f"功能配置错误: {str(e)}")
    except Exception as e:
        st.error(f"页面渲染错误: {str(e)}")
        logger.error(f"Page rendering error: {str(e)}")


if check_password():
    main()
