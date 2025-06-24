#!/usr/bin/env python3
"""
健康检查脚本
检查RevClaudeAPI服务是否正常运行
"""

import sys
import time

try:
    import urllib.error
    import urllib.request
except ImportError:
    print("urllib not available")
    sys.exit(1)


def check_health():
    """检查服务健康状态"""
    try:
        # 检查轻量级健康端点
        response = urllib.request.urlopen("http://localhost:1145/health", timeout=5)
        if response.status == 200:
            print("Health check passed")
            return True
    except urllib.error.URLError as e:
        print(f"Health check failed: {e}")
        return False
    except Exception as e:
        print(f"Health check error: {e}")
        return False

    return False


if __name__ == "__main__":
    if check_health():
        sys.exit(0)  # 健康
    else:
        sys.exit(1)  # 不健康
