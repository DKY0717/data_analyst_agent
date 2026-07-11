# 健康检查与监控 API 模块
# 提供 /health、/health/cache、/health/metrics、/health/ab-tests 端点

import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List
from ..config import settings
from ..models.schemas import SuccessResponse
from ..services.query_cache import query_cache
from ..services.prompt_registry import prompt_registry
from ..services.ab_test import ab_test_registry, ABTest, ABTestVariant
from ..db.connection import db_connection
from ..security import auth as auth_security
from ..security.auth import AuthUser, require_management_user

router = APIRouter()

# 服务启动时间
_start_time = time.time()

REQUIRED_BUSINESS_TABLES = (
    "regions",
    "customers",
    "categories",
    "products",
    "orders",
    "order_items",
    "payments",
    "refunds",
)

REQUIRED_NON_EMPTY_TABLES = (
    "regions",
    "customers",
    "categories",
    "products",
    "orders",
    "order_items",
    "payments",
)


def _secure_profile_errors() -> list[str]:
    """受保护部署缺少认证或隔离时拒绝 readiness，不静默降级为开放模式。"""
    if settings.DEPLOYMENT_PROFILE != "secure":
        return []

    errors = []
    if not settings.SANDBOX_MODE:
        errors.append("sandbox_disabled")
    if not auth_security.has_secure_auth_configuration():
        errors.append("authentication_missing_or_weak")
    if settings.AUTH_DEMO_ENABLED:
        errors.append("demo_auth_enabled")
    if settings.AUTH_PASSWORD_LOGIN_ENABLED:
        weak_passwords = {"admin", "password", "changeme", "123456"}
        if (
            not settings.AUTH_ADMIN_USERNAME
            or len(settings.AUTH_ADMIN_PASSWORD) < 12
            or settings.AUTH_ADMIN_PASSWORD.casefold() in weak_passwords
        ):
            errors.append("admin_credentials_missing_or_weak")
    return errors


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


def _execute_fetchall(conn, backend: str, sql: str, params=None):
    if backend == "postgresql":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    return conn.execute(sql, params or []).fetchall()


def _execute_fetchone(conn, backend: str, sql: str, params=None):
    if backend == "postgresql":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchone()
    return conn.execute(sql, params or []).fetchone()


def _assert_business_database_ready(conn, backend: str) -> dict:
    """确认数据库不只是能连接，还具备 NL2SQL 演示所需的核心表和数据。"""
    schema_name = "public" if backend == "postgresql" else "main"
    table_rows = _execute_fetchall(
        conn,
        backend,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
        """
        if backend == "postgresql"
        else """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = ?
        """,
        [schema_name],
    )
    existing_tables = {row[0] for row in table_rows}
    missing_tables = sorted(set(REQUIRED_BUSINESS_TABLES) - existing_tables)
    if missing_tables:
        raise RuntimeError(f"missing business tables: {', '.join(missing_tables)}")

    row_counts = {}
    for table in REQUIRED_NON_EMPTY_TABLES:
        # 表名来自固定白名单，不接受外部输入，避免 health check 引入 SQL 注入面。
        row_counts[table] = _execute_fetchone(
            conn,
            backend,
            f"SELECT COUNT(*) FROM {table}",
        )[0]

    empty_tables = [table for table, count in row_counts.items() if count <= 0]
    if empty_tables:
        raise RuntimeError(f"empty business tables: {', '.join(empty_tables)}")

    return row_counts


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
    """就绪检查端点：确认 API 进程、数据库结构和演示数据均可用。"""
    if _secure_profile_errors():
        raise HTTPException(status_code=503, detail="服务未就绪")
    try:
        with db_connection.get_session() as conn:
            _execute_fetchone(conn, db_connection.backend, "SELECT 1")
            row_counts = _assert_business_database_ready(conn, db_connection.backend)
    except Exception:
        raise HTTPException(status_code=503, detail="服务未就绪") from None

    return SuccessResponse(
        code=200,
        message="success",
        data={
            "status": "ready",
            "deployment_profile": settings.DEPLOYMENT_PROFILE,
            "sql_execution": {
                "mode": "sandbox" if settings.SANDBOX_MODE else "direct",
                "timeout_seconds": settings.SQL_TIMEOUT,
                "isolated": settings.SANDBOX_MODE,
            },
            "database": {
                "ok": True,
                "backend": db_connection.backend,
                "required_tables": list(REQUIRED_BUSINESS_TABLES),
                "row_counts": row_counts,
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
