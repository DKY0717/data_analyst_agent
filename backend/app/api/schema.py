# Schema 查询 API 模块
# 提供 /api/schema 端点，返回数据库表结构信息

from fastapi import APIRouter, HTTPException
from ..models.schemas import SuccessResponse, SchemaResponse
from ..db.schema_loader import schema_loader
from ..utils.logger import logger
from ..utils.exceptions import SchemaLoadError

router = APIRouter()


@router.get("/api/schema", response_model=SuccessResponse)
async def get_schema():
    """获取数据库 Schema，包含所有表的列信息和主键"""
    try:
        schema = schema_loader.get_full_schema()
        return SuccessResponse(
            code=200,
            message="success",
            data=SchemaResponse(**schema)
        )
    except SchemaLoadError as e:
        logger.error("Schema 加载失败: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="Schema 加载失败") from e
    except Exception as e:
        logger.error("Schema 查询异常: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="Internal server error") from e
