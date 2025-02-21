import os

ADMIN_USERNAME = "claude-backend"
ADMIN_PASSWORD = "20Wd!!!!"

CLAUDE_BACKEND_API_BASE_URL = "https://clauai.qqyunsd.com/adminapi"
CLAUDE_BACKEND_API_USER_URL = f"{CLAUDE_BACKEND_API_BASE_URL}/chatgpt/user/"
CLAUDE_BACKEND_API_APIAUTH = "ccccld"


BASE_URL = os.environ.get("BASE_URL", f"http://54.254.143.80:1145")


API_KEY_ROUTER = f"{BASE_URL}/api/v1/api_key"
API_CLAUDE35_URL = "https://api.claude35.585dg.com/api/v1"
