import requests


def stream_response(url, payload, headers):
    # 发起一个流式的 POST 请求
    with requests.post(url, json=payload, headers=headers, stream=True) as response:
        # 逐个字符处理响应体
        print(f"headers: {response.headers}")
        for chunk in response.iter_content(
            decode_unicode=True, chunk_size=1
        ):  # 设置chunk_size为1来逐个字符获取
            if chunk:  # 过滤掉keep-alive新行
                print(chunk, end="")  # 打印每个字符，end='' 防止自动换行


# 你的API URL
url = "http://23.94.133.68:6238/api/v1/claude/chat"

# 你的请求头

headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "sj-731ce22577ac49339dd0b6a5bc49a9b2",
}

# 你的请求体
data = {
    "message": "你好，你能干什么？",
    "model": "claude-3-opus-20240229",
    "stream": True,
}

# 调用函数
stream_response(url, data, headers)
