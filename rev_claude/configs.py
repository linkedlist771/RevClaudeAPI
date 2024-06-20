from httpx import Timeout


API_KEY_REFRESH_INTERVAL_HOURS = 3

API_KEY_REFRESH_INTERVAL = API_KEY_REFRESH_INTERVAL_HOURS * 60 * 60
BASIC_KEY_MAX_USAGE = 20
PLUS_KEY_MAX_USAGE = 40


STREAM_CONNECTION_TIME_OUT = 60
STREAM_READ_TIME_OUT = 60
STREAM_POOL_TIME_OUT = 10 * 60


# 设置连接超时为你的 STREAM_CONNECTION_TIME_OUT，其他超时设置为无限
STREAM_TIMEOUT = Timeout(
    connect=STREAM_CONNECTION_TIME_OUT,  # 例如设为 10 秒
    read=STREAM_READ_TIME_OUT,  # 例如设为 5 秒
    write=None,
    pool=STREAM_POOL_TIME_OUT,  # 例如设为 10 分钟
)

USE_PROXY = False

PROXIES = {
    'http://': 'socks5://127.0.0.1:7891',
    'https://': 'socks5://127.0.0.1:7891'
}


DOCS_USERNAME = "claude-backend"
DOCS_PASSWORD = "20Wd!!!!"
