#!/bin/bash

echo "=== 容器重启诊断脚本 ==="
echo "时间: $(date)"

# 检查容器状态
echo "=== 检查容器状态 ==="
docker ps -a | grep revclaudeapi

# 检查容器日志 (最后50行)
echo ""
echo "=== 检查容器日志 ==="
CONTAINER_ID=$(docker ps -a | grep revclaudeapi | grep node-serve-front | awk '{print $1}')
if [ ! -z "$CONTAINER_ID" ]; then
    echo "容器ID: $CONTAINER_ID"
    docker logs --tail 50 $CONTAINER_ID
else
    echo "未找到容器"
fi

# 检查健康状态
echo ""
echo "=== 检查健康状态 ==="
docker inspect $CONTAINER_ID | jq '.[0].State.Health' 2>/dev/null || echo "无健康检查信息"

# 检查退出代码
echo ""
echo "=== 检查退出代码 ==="
docker inspect $CONTAINER_ID | jq '.[0].State.ExitCode' 2>/dev/null || echo "无退出代码信息"

# 检查Redis连接
echo ""
echo "=== 检查Redis连接 ==="
REDIS_CONTAINER=$(docker ps | grep redis | awk '{print $1}')
if [ ! -z "$REDIS_CONTAINER" ]; then
    echo "Redis容器运行正常: $REDIS_CONTAINER"
    docker exec $REDIS_CONTAINER redis-cli ping 2>/dev/null || echo "Redis连接失败"
else
    echo "Redis容器未运行"
fi

# 检查端口占用
echo ""
echo "=== 检查端口占用 ==="
ss -tlnp | grep -E ':(1145|5000|6379)' || echo "端口未被占用"

# 检查系统资源
echo ""
echo "=== 检查系统资源 ==="
echo "内存使用:"
free -h
echo "磁盘使用:"
df -h | head -5

# 手动测试健康检查端点
echo ""
echo "=== 手动测试健康检查端点 ==="
if [ ! -z "$CONTAINER_ID" ]; then
    echo "尝试在容器内测试健康检查..."
    docker exec $CONTAINER_ID curl -f http://localhost:1145/api/v1/clients_status 2>/dev/null && echo "健康检查成功" || echo "健康检查失败"
fi

echo ""
echo "=== 诊断完成 ===" 