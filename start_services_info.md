# 启动服务脚本说明

## 🚀 启动顺序优化

### 原始问题
- ❌ Streamlit 先启动（不重要的前端服务）
- ❌ API 后启动（重要的核心服务）
- ❌ 没有检查服务就绪状态

### 优化后的启动顺序

1. **启动 API 服务** (优先级最高)
   ```bash
   python /workspace/main.py --port 1145 --host 0.0.0.0 &
   ```

2. **等待 API 服务就绪** (最多等待60秒)
   ```bash
   for i in {1..30}; do
       if python /workspace/health_check.py 2>/dev/null; then
           echo "API service is ready!"
           break
       fi
       echo "Waiting for API... ($i/30)"
       sleep 2
   done
   ```

3. **启动 Streamlit 前端** (依赖 API 服务)
   ```bash
   streamlit run /workspace/front_python/front_manager.py \
       --server.port 5000 \
       --server.headless true \
       --server.address 0.0.0.0 &
   ```

## 🔄 监控逻辑优化

### 进程监控顺序
1. **优先检查 API 服务** - 核心服务，必须保持运行
2. **然后检查 Streamlit** - 前端服务，依赖API

### 重启逻辑
- API 挂掉 → 立即重启，等待5秒后再检查其他服务
- Streamlit 挂掉 → 先检查API是否正常，再决定是否重启前端

## ✅ 优势

1. **服务重要性优先级** - API > Streamlit
2. **依赖关系明确** - Streamlit 依赖 API
3. **健康检查集成** - 使用 `/health` 端点验证服务状态
4. **容错能力强** - 智能重启逻辑

## 🎯 适用场景

- RevClaudeAPI 为核心服务
- Streamlit 为可选的前端界面
- 需要高可用性的API服务 