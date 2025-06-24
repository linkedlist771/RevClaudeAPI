import os
from pathlib import Path

import redis

ADMIN_USERNAME = "claude-backend"
ADMIN_PASSWORD = "20Wd!!!!"

CLAUDE_BACKEND_API_BASE_URL = "https://clauai.qqyunsd.com/adminapi"
CLAUDE_BACKEND_API_USER_URL = f"{CLAUDE_BACKEND_API_BASE_URL}/chatgpt/user/"
CLAUDE_BACKEND_API_APIAUTH = "ccccld"


BASE_URL = os.environ.get("BASE_URL", f"http://54.254.143.80:1145")


API_KEY_ROUTER = f"{BASE_URL}/api/v1/api_key"
API_CLAUDE35_URL = "https://api.claude35.585dg.com/api/v1"

CLAUDE_AUDIT_BASE_URL = "http://54.254.143.80:8090"

ROOT = Path(__file__).parent.parent

STREAMLIT_LOGS = ROOT / "streamlit_logs"
STREAMLIT_LOGS.mkdir(exist_ok=True, parents=True)

HTTP_TIMEOUT = 3600

# Redis 连接设置
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)


if __name__ == "__main__":
    print(STREAMLIT_LOGS)
