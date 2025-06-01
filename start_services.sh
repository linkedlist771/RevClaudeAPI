#!/bin/bash

# 创建日志目录
mkdir -p /workspace/streamlit_logs

echo "Starting RevClaudeAPI services..."

# 启动 Streamlit 前端服务
echo "Starting Streamlit frontend service..."
streamlit run /workspace/front_python/front_manager.py \
    --server.port 5000 \
    --server.headless true \
    --server.address 0.0.0.0 \
    > /workspace/streamlit_logs/streamlit.log 2>&1 &

STREAMLIT_PID=$!
echo "Streamlit started with PID: $STREAMLIT_PID"

# 等待 Streamlit 启动
sleep 10

# 启动主 API 服务
echo "Starting main API service..."
python /workspace/main.py --port 1145 --host 0.0.0.0 &

API_PID=$!
echo "API service started with PID: $API_PID"

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

# 监控进程
while true; do
    if ! kill -0 $STREAMLIT_PID 2>/dev/null; then
        echo "Streamlit process died, restarting..."
        streamlit run /workspace/front_python/front_manager.py \
            --server.port 5000 \
            --server.headless true \
            --server.address 0.0.0.0 \
            > /workspace/streamlit_logs/streamlit.log 2>&1 &
        STREAMLIT_PID=$!
    fi
    
    if ! kill -0 $API_PID 2>/dev/null; then
        echo "API process died, restarting..."
        python /workspace/main.py --port 1145 --host 0.0.0.0 &
        API_PID=$!
    fi
    
    sleep 30
done 