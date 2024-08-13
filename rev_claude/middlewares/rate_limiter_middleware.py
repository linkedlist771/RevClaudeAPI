from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Awaitable, Dict
import time


class InMemoryRateLimiter:
    def __init__(self, rate_per_minute: int):
        self.rate_per_minute = rate_per_minute
        self.window = 60  # 1 minute in seconds
        self.requests: Dict[str, list] = {}

    def hit(self, key: str) -> bool:
        now = time.time()
        self.requests.setdefault(key, [])
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]

        if len(self.requests[key]) >= self.rate_per_minute:
            return False

        self.requests[key].append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: FastAPI,
        rate_per_minute: int = 100,
        identifier: Callable[[Request], Awaitable[str]] = None,
        callback: Callable[[Request], Awaitable[JSONResponse]] = None,
    ):
        super().__init__(app)
        self.limiter = InMemoryRateLimiter(rate_per_minute)
        self.identifier = identifier or self.default_identifier
        self.callback = callback or self.default_callback

    async def default_identifier(self, request: Request) -> str:
        return request.client.host

    async def default_callback(self, request: Request) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    async def dispatch(self, request: Request, call_next):
        key = await self.identifier(request)

        if not self.limiter.hit(key):
            return await self.callback(request)

        response = await call_next(request)
        return response


# 使用示例
# app = FastAPI()
#
# # 添加中间件
# app.add_middleware(
#     RateLimitMiddleware,
#     rate_per_minute=100
# )
#
#
# @app.get("/")
# async def root():
#     return {"message": "Hello World"}
#
#
# if __name__ == "__main__":
#     import uvicorn
#
#     uvicorn.run(app, host="0.0.0.0", port=8000)
