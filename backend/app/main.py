# FastAPI 应用入口模块
# 创建 FastAPI 实例，注册路由和中间件

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings, ensure_directories
from .api import health, schema, query
from .utils.logger import logger

# 创建 FastAPI 应用
app = FastAPI(
    title="Data Analyst Agent",
    description="自然语言驱动的数据库分析与 SQL 优化系统",
    version="1.0.0"
)

# CORS 中间件，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router)
app.include_router(schema.router)
app.include_router(query.router)


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化目录和日志"""
    ensure_directories()
    logger.info("Data Analyst Agent API 启动")
    logger.info(f"数据库路径: {settings.DATA_DIR}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("Data Analyst Agent API 关闭")
