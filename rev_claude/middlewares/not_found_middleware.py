from fastapi import FastAPI, Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware


# 自定义中间件
class NotFoundResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 404:
            # 关闭连接，不返回响应
            return Response(content="", status_code=204)
        return response
