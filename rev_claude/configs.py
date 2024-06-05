from httpx import Timeout


API_KEY_REFRESH_INTERVAL_HOURS = 3

API_KEY_REFRESH_INTERVAL = API_KEY_REFRESH_INTERVAL_HOURS * 60 * 60
BASIC_KEY_MAX_USAGE = 100
PLUS_KEY_MAX_USAGE = 40


STREAM_CONNECTION_TIME_OUT = 10



# 设置连接超时为你的 STREAM_CONNECTION_TIME_OUT，其他超时设置为无限
STREAM_TIMEOUT = Timeout(
    connect=STREAM_CONNECTION_TIME_OUT,  # 例如设为 10 秒
    read=None,
    write=None,
    pool=None  # pool是用于控制从连接池中获取连接的超时时间
)