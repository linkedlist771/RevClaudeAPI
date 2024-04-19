import requests


def stream_response(url, payload, headers):
    # 发起一个流式的 POST 请求
    response = requests.post(url, json=payload, headers=headers, stream=True)

    # 检查响应是否成功
    if response.status_code == 200:
        # 逐个字符处理响应体
        for chunk in response.iter_content(decode_unicode=True, chunk_size=1):  # 设置chunk_size为1来逐个字符获取
            if chunk:  # 过滤掉keep-alive新行
                print(chunk, end='')  # 打印每个字符，end='' 防止自动换行
    else:
        print(f"Failed to get stream: {response.status_code}")


# 你的API URL
url = 'http://198.23.176.34:6238/api/v1/claude/chat'

# 你的请求头
headers = {
    'accept': 'application/json',
    'Content-Type': 'application/json'
}

# 你的请求体
data = {
    "message": "Hello, how are you? Doyou",
    "model": "claude-3-sonnet-20240229",
    "stream": True
}

# 调用函数
stream_response(url, data, headers)
