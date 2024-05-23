from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
import time
import uvicorn
import asyncio

app = FastAPI()


async def generate_data():
    """生成器函数，每秒输出当前时间戳"""

    for _ in range(10):
        yield f"data: {time.time()}\n\n"
        await asyncio.sleep(0.2)  # 模拟异步操作, 让出权限


async def patched_generate_data(original_generator, conversation_id):
    # 首先发送 conversation_id
    yield f"<{conversation_id}>"

    # 然后，对原始生成器进行迭代，产生剩余的数据
    async for data in original_generator:
        yield data


@app.post("/stream")
async def stream():
    """返回一个流式响应，客户端将逐步接收数据"""

    r = generate_data()
    r = patched_generate_data(r, "test")
    return StreamingResponse(
        r, media_type="text/event-stream", headers={"conversation_id": "test"}
    )


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件接口"""
    # if file.filename.endswith(".txt"):
    if True:
        return JSONResponse(
            content={
                "file_name": file.filename,
                "file_type": file.content_type,
            }
        )
    else:
        return JSONResponse(status_code=400, content={"message": "只支持.txt文件"})

@app.get("/health")
async def health():
    return {"status": "ok"}

# cross origin
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 请根据需要调整此设置
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
config = uvicorn.Config(app, host="0.0.0.0", port=8848)
server = uvicorn.Server(config=config)
server.run()
