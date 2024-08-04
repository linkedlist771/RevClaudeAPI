import streamlit as st
import requests
import pandas as pd
import altair as alt
from tqdm import tqdm
from urllib.request import urlopen


def get_public_ip():
    try:
        response = urlopen("https://api.ipify.org")
        return response.read().decode("utf-8")
    except:
        return None


# claude3.ucas.life
BASE_URL = f"http://60.205.189.192:1145"
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
        expiration_days = st.number_input("过期天数", min_value=1, value=1, step=1)
        key_type = st.text_input("密钥类型", value="plus")
        key_number = st.number_input("密钥数量", min_value=1, value=1, step=1)

        if st.button("创建API密钥"):
            url = f"{BASE_URL}/api/v1/api_key/create_key"
            payload = {
                "expiration_days": expiration_days,
                "key_type": key_type,
                "key_number": key_number,
            }
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                st.success(response.json())
            else:
                st.error("API密钥创建失败。")

    elif api_key_function == "验证API密钥":
        st.subheader("验证API密钥")
        api_key = st.text_input("API密钥")

        if st.button("验证API密钥"):
            url = f"{BASE_URL}/api/v1/api_key/validate_key/{api_key}"
            response = requests.get(url)
            if response.status_code == 200:
                st.success("API密钥有效。")
            else:
                st.error("API密钥无效。")

    elif api_key_function == "删除API密钥":
        st.subheader("删除API密钥")
        api_key_to_delete = st.text_input("要删除的API密钥")

        if st.button("删除API密钥"):
            url = f"{BASE_URL}/api/v1/api_key/delete_key/{api_key_to_delete}"
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
                url = f"{BASE_URL}/api/v1/api_key/delete_batch_keys"
                headers = {"Content-Type": "application/json"}
                data = {"api_keys": api_keys_list}

                response = requests.delete(url, headers=headers, json=data)

                if response.status_code == 200:
                    st.success(f"成功删除 {len(api_keys_list)} 个API密钥。")
                    st.write(response.json())
                else:
                    st.error("批量删除API密钥失败。")
                    st.write(response.text)
            else:
                st.warning("请输入至少一个API密钥进行删除。")

    elif api_key_function == "获取所有API密钥":
        st.subheader("获取所有API密钥")

        if st.button("获取所有API密钥"):
            url = f"{BASE_URL}/api/v1/api_key/list_keys"
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
            url = f"{BASE_URL}/api/v1/api_key/list_keys"
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
            url = f"{BASE_URL}/api/v1/api_key/get_information/{api_key}"
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
            url = f"{BASE_URL}/api/v1/reset_current_usage/{api_key_to_reset}"
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
            url = f"{BASE_URL}/api/v1/extend_expiration/{api_key_to_extend}"
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
        ["上传Cookie", "删除Cookie", "刷新Cookie", "列出所有Cookie", "更新Cookie"],
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
