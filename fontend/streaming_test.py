from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import time
import uvicorn
import asyncio

app = FastAPI()

async def generate_data():
    """生成器函数，每秒输出当前时间戳"""
    for _ in range(10):
        yield f"data: {time.time()}\n\n"
        await asyncio.sleep(0)  # 模拟异步操作, 让出权限

@app.post("/stream")
async def stream():
    """返回一个流式响应，客户端将逐步接收数据"""
    r = generate_data()
    return StreamingResponse(r, media_type="text/event-stream")


config = uvicorn.Config(app, host="0.0.0.0", port=8848)
server = uvicorn.Server(config=config)
server.run()
