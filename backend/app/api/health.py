# 健康检查与监控 API 模块
# 提供 /health、/health/cache、/health/metrics、/health/ab-tests 端点

import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from ..models.schemas import SuccessResponse
from ..services.query_cache import query_cache
from ..services.prompt_registry import prompt_registry
from ..services.ab_test import ab_test_registry, ABTest, ABTestVariant
from ..agents.session_store import session_store

router = APIRouter()

# 服务启动时间
_start_time = time.time()


class ABTestCreateRequest(BaseModel):
    test_id: str
    description: str
    variants: List[dict]  # [{"name": "control", "prompt_name": "generate_sql", "prompt_version": 1, "weight": 1.0}]


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


@router.get("/health/ab-tests", response_model=SuccessResponse)
async def list_ab_tests():
    """列出所有 A/B 测试"""
    tests = ab_test_registry.list_tests()
    return SuccessResponse(
        code=200,
        message="success",
        data=tests
    )


@router.post("/health/ab-tests", response_model=SuccessResponse)
async def create_ab_test(request: ABTestCreateRequest):
    """创建一个 A/B 测试"""
    variants = []
    for v in request.variants:
        variants.append(ABTestVariant(
            name=v["name"],
            prompt_name=v["prompt_name"],
            prompt_version=v["prompt_version"],
            weight=v.get("weight", 1.0),
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
async def ab_test_report(test_id: str):
    """获取 A/B 测试对比报告"""
    report = ab_test_registry.get_report(test_id)
    if not report.get("variants"):
        raise HTTPException(status_code=404, detail=f"A/B 测试 {test_id} 无数据")
    return SuccessResponse(
        code=200,
        message="success",
        data=report
    )
