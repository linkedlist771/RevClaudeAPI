
from pathlib import Path
import os
TARGET_URL = "https://soruxgpt-saas-liuli.soruxgpt.com"
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

ROOT = Path(__file__).parent
JS_DIR = ROOT / "js"
IMAGES_DIR = ROOT / "images"
IMAGES_DIR.mkdir(exist_ok=True)
JS_DIR.mkdir(exist_ok=True)

if __name__ == "__main__":
    print(ROOT)

    # js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "js")
    # print(js_dir)

# js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "js")
