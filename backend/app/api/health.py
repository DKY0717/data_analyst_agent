# 健康检查与监控 API 模块
# 提供 /health、/health/cache、/health/metrics、/health/ab-tests 端点

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List
from ..models.schemas import SuccessResponse
from ..services.query_cache import query_cache
from ..services.prompt_registry import prompt_registry
from ..services.ab_test import ab_test_registry, ABTest, ABTestVariant
from ..db.connection import db_connection
from ..security.auth import AuthUser, require_management_user

router = APIRouter()

# 服务启动时间
_start_time = time.time()


class ABTestVariantCreateRequest(BaseModel):
    """A/B 测试变体请求模型：在进入注册逻辑前拦截缺字段和非法权重。"""
    name: str = Field(..., min_length=1, max_length=64)
    prompt_name: str = Field(..., min_length=1, max_length=128)
    prompt_version: int = Field(..., ge=1)
    weight: float = Field(1.0, gt=0)


class ABTestCreateRequest(BaseModel):
    """A/B 测试创建请求模型，避免裸 dict 导致管理接口 500。"""
    test_id: str = Field(..., min_length=1, max_length=128)
    description: str = Field(..., min_length=1, max_length=500)
    variants: List[ABTestVariantCreateRequest] = Field(..., min_length=1)


@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """存活检查端点：确认 API 进程仍在响应。"""
    return SuccessResponse(
        code=200,
        message="success",
        data={"status": "healthy"}
    )


@router.get("/health/readiness", response_model=SuccessResponse)
async def readiness_check():
    """就绪检查端点：确认 API 进程和数据库连接均可用。"""
    try:
        with db_connection.get_session() as conn:
            if db_connection.backend == "postgresql":
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            else:
                conn.execute("SELECT 1").fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="服务未就绪") from None

    return SuccessResponse(
        code=200,
        message="success",
        data={
            "status": "ready",
            "database": {
                "ok": True,
                "backend": db_connection.backend,
            },
        }
    )


@router.get("/health/cache", response_model=SuccessResponse)
async def cache_stats(_: AuthUser | None = Depends(require_management_user)):
    """缓存统计端点"""
    stats = query_cache.stats()
    return SuccessResponse(
        code=200,
        message="success",
        data=stats
    )


@router.get("/health/metrics", response_model=SuccessResponse)
async def metrics(_: AuthUser | None = Depends(require_management_user)):
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


@router.get("/health/ab-tests", response_model=SuccessResponse)
async def list_ab_tests(_: AuthUser | None = Depends(require_management_user)):
    """列出所有 A/B 测试"""
    tests = ab_test_registry.list_tests()
    return SuccessResponse(
        code=200,
        message="success",
        data=tests
    )


@router.post("/health/ab-tests", response_model=SuccessResponse)
async def create_ab_test(
    request: ABTestCreateRequest,
    _: AuthUser | None = Depends(require_management_user),
):
    """创建一个 A/B 测试"""
    variants = []
    for v in request.variants:
        variants.append(ABTestVariant(
            name=v.name,
            prompt_name=v.prompt_name,
            prompt_version=v.prompt_version,
            weight=v.weight,
        ))

    test = ABTest(
        test_id=request.test_id,
        description=request.description,
        variants=variants,
    )
    ab_test_registry.register(test)

    return SuccessResponse(
        code=200,
        message="success",
        data={"test_id": request.test_id, "variants": len(variants)}
    )


@router.get("/health/ab-tests/{test_id}/report", response_model=SuccessResponse)
async def ab_test_report(
    test_id: str,
    _: AuthUser | None = Depends(require_management_user),
):
    """获取 A/B 测试对比报告"""
    report = ab_test_registry.get_report(test_id)
    if not report.get("variants"):
        raise HTTPException(status_code=404, detail=f"A/B 测试 {test_id} 无数据")
    return SuccessResponse(
        code=200,
        message="success",
        data=report
    )
