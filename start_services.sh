#!/bin/bash

# 创建日志目录
mkdir -p /workspace/streamlit_logs

echo "Starting RevClaudeAPI services..."

# 先启动主 API 服务（更重要的核心服务）
echo "Starting main API service..."
python /workspace/main.py --port 1145 --host 0.0.0.0 &

API_PID=$!
echo "API service started with PID: $API_PID"

# 等待 API 服务启动并检查健康状态
echo "Waiting for API service to be ready..."
for i in {1..30}; do
    if python /workspace/health_check.py 2>/dev/null; then
        echo "API service is ready!"
        break
    fi
    echo "Waiting for API... ($i/30)"
    sleep 2
done

# 启动 Streamlit 前端服务
echo "Starting Streamlit frontend service..."
streamlit run /workspace/front_python/front_manager.py \
    --server.port 5000 \
    --server.headless true \
    --server.address 0.0.0.0 \
    > /workspace/streamlit_logs/streamlit.log 2>&1 &

STREAMLIT_PID=$!
echo "Streamlit started with PID: $STREAMLIT_PID"

# 创建清理函数
cleanup() {
    echo "Shutting down services..."
    kill $STREAMLIT_PID $API_PID 2>/dev/null
    wait $STREAMLIT_PID $API_PID 2>/dev/null
    echo "Services stopped."
    exit 0
}

# 捕获信号
trap cleanup SIGTERM SIGINT

# 监控进程（优先检查API服务）
while true; do
    # 优先检查API服务（核心服务）
    if ! kill -0 $API_PID 2>/dev/null; then
        echo "API process died, restarting..."
        python /workspace/main.py --port 1145 --host 0.0.0.0 &
        API_PID=$!
        # API重启后，等待一会再检查Streamlit
        sleep 5
    fi
    
    # 检查Streamlit前端服务
    if ! kill -0 $STREAMLIT_PID 2>/dev/null; then
        echo "Streamlit process died, restarting..."
        # 确保API服务正常后再重启Streamlit
        if python /workspace/health_check.py 2>/dev/null; then
            streamlit run /workspace/front_python/front_manager.py \
                --server.port 5000 \
                --server.headless true \
                --server.address 0.0.0.0 \
                > /workspace/streamlit_logs/streamlit.log 2>&1 &
            STREAMLIT_PID=$!
        else
            echo "API service not ready, waiting before restarting Streamlit..."
        fi
    fi
    
    sleep 30
done 