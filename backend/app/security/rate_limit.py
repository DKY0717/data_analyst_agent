"""速率限制模块：基于 slowapi 的请求限流。"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# 从环境变量读取限流配置
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "30/minute")
RATE_LIMIT_QUERY = os.getenv("RATE_LIMIT_QUERY", "10/minute")
RATE_LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "5/minute")


def _get_client_id(request: Request) -> str:
    """优先使用 API Key 或用户 ID 作为限流键，其次用 IP。"""
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return f"apikey:{api_key[:8]}"
    auth = request.headers.get("Authorization", "")
    if auth:
        return f"auth:{auth[:16]}"
    return get_remote_address(request)


limiter = Limiter(key_func=_get_client_id)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """自定义限流错误响应。"""
    return JSONResponse(
        status_code=429,
        content={
            "code": 429,
            "message": f"请求过于频繁，请稍后重试。限制：{exc.detail}",
            "data": None,
        },
    )


def setup_rate_limit(app: FastAPI) -> None:
    """在 FastAPI 应用上配置速率限制。"""
    from slowapi.middleware import SlowAPIMiddleware

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
