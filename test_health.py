#!/usr/bin/env python3
"""
测试健康检查端点
"""

import sys

try:
    import json
    import urllib.error
    import urllib.request
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def test_health_endpoints():
    """测试所有健康检查端点"""
    endpoints = ["http://localhost:1145/health", "http://localhost:1145/api/v1/health"]

    for endpoint in endpoints:
        print(f"\n测试端点: {endpoint}")
        try:
            response = urllib.request.urlopen(endpoint, timeout=5)
            if response.status == 200:
                data = response.read().decode("utf-8")
                try:
                    json_data = json.loads(data)
                    print(f"✅ 成功: {json_data}")
                except json.JSONDecodeError:
                    print(f"✅ 成功: {data}")
            else:
                print(f"❌ 失败: HTTP {response.status}")
        except urllib.error.URLError as e:
            print(f"❌ 连接失败: {e}")
        except Exception as e:
            print(f"❌ 错误: {e}")


if __name__ == "__main__":
    print("RevClaudeAPI 健康检查端点测试")
    print("=" * 40)
    test_health_endpoints()
    print("\n测试完成")
