# FastAPI 应用入口模块
# 创建 FastAPI 实例，注册路由和中间件

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings, ensure_directories
from .api import health, schema, query, auth_router
from .security.rate_limit import setup_rate_limit
from .services.tracing import init_tracing
from .utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化，关闭时清理"""
    ensure_directories()
    init_tracing()
    logger.info("Data Analyst Agent API 启动")
    logger.info(f"数据库路径: {settings.DATA_DIR}")
    yield
    logger.info("Data Analyst Agent API 关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="Data Analyst Agent",
    description="自然语言驱动的数据库分析与 SQL 优化系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置速率限制
setup_rate_limit(app)

# CORS 中间件只允许配置的前端来源，避免生产环境默认开放任意 Origin。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router)
app.include_router(schema.router)
app.include_router(query.router)
app.include_router(auth_router.router)
