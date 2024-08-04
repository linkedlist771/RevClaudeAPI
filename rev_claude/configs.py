from httpx import Timeout
from pathlib import Path

API_KEY_REFRESH_INTERVAL_HOURS = 3
ROOT = Path(__file__).parent.parent
API_KEY_REFRESH_INTERVAL = API_KEY_REFRESH_INTERVAL_HOURS * 60 * 60
BASIC_KEY_MAX_USAGE = 10
PLUS_KEY_MAX_USAGE = 60

ACCOUNT_DELETE_LIMIT = 150


STREAM_CONNECTION_TIME_OUT = 60
STREAM_READ_TIME_OUT = 60
STREAM_POOL_TIME_OUT = 10 * 60


NEW_CONVERSATION_RETRY = 5

# 设置连接超时为你的 STREAM_CONNECTION_TIME_OUT，其他超时设置为无限
STREAM_TIMEOUT = Timeout(
    connect=STREAM_CONNECTION_TIME_OUT,  # 例如设为 10 秒
    read=STREAM_READ_TIME_OUT,  # 例如设为 5 秒
    write=None,
    pool=STREAM_POOL_TIME_OUT,  # 例如设为 10 分钟
)

USE_PROXY = False
USE_MERMAID_AND_SVG = True

PROXIES = {"http://": "socks5://127.0.0.1:7891", "https://": "socks5://127.0.0.1:7891"}

REDIS_HOST = "localhost"
REDIS_PORT = 6379


DOCS_USERNAME = "claude-backend"
DOCS_PASSWORD = "20Wd!!!!"


# Claude 官方镜像的链接w

CLAUDE_OFFICIAL_REVERSE_BASE_URL: str = "https://ai.liuli.arelay.com"

# 三小时
CLAUDE_OFFICIAL_EXPIRE_TIME = 3 * 60 * 60


# 每次使用都会增加20次次数
CLAUDE_OFFICIAL_USAGE_INCREASE = 15


"""
这里是对Poe后端的定义
"""
POE_BOT_BASE_URL = "https://api.poe.com/bot/"
POE_BOT_TEMPERATURE = 0.95


if __name__ == "__main__":
    from loguru import logger
    logger.info(ROOT)