# 健康检查与监控 API 模块
# 提供 /health、/health/cache、/health/metrics 端点

import time
from fastapi import APIRouter
from ..models.schemas import SuccessResponse
from ..services.query_cache import query_cache
from ..services.prompt_registry import prompt_registry
from ..agents.session_store import session_store

router = APIRouter()

# 服务启动时间
_start_time = time.time()


@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """健康检查端点，返回服务状态"""
    return SuccessResponse(
        code=200,
        message="success",
        data={"status": "healthy"}
    )


@router.get("/health/cache", response_model=SuccessResponse)
async def cache_stats():
    """缓存统计端点"""
    stats = query_cache.stats()
    return SuccessResponse(
        code=200,
        message="success",
        data=stats
    )


@router.get("/health/metrics", response_model=SuccessResponse)
async def metrics():
    """综合监控指标端点"""
    uptime_seconds = int(time.time() - _start_time)
    cache = query_cache.stats()

    return SuccessResponse(
        code=200,
        message="success",
        data={
            "uptime_seconds": uptime_seconds,
            "cache": cache,
            "prompts": {
                "generate_sql": len(prompt_registry.list_versions("generate_sql")),
                "repair_sql": len(prompt_registry.list_versions("repair_sql")),
                "generate_answer": len(prompt_registry.list_versions("generate_answer")),
            },
        }
    )
