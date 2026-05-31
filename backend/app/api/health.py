# 健康检查 API 模块
# 提供 /health 端点，用于监控服务状态

from fastapi import APIRouter
from ..models.schemas import SuccessResponse

router = APIRouter()


@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """健康检查端点，返回服务状态"""
    return SuccessResponse(
        code=200,
        message="success",
        data={"status": "healthy"}
    )
