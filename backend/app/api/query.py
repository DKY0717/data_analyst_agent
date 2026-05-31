# 查询 API 模块
# 提供 /api/chat/query 端点，是整个系统的核心入口
# 接收自然语言问题，调用 AgentGraph 工作流，返回完整的分析结果

from fastapi import APIRouter, HTTPException
from ..models.schemas import QueryRequest, QueryResponse, SuccessResponse
from ..agents.graph import agent_graph
from ..utils.logger import logger

router = APIRouter()


@router.post("/api/chat/query", response_model=SuccessResponse)
async def query(request: QueryRequest):
    """处理自然语言查询，返回 SQL、查询结果和自然语言解释

    完整流程:
    1. AgentGraph 加载 Schema
    2. LLM 生成 SQL
    3. SQL Guard 安全校验
    4. 执行 SQL 查询
    5. 如失败则 LLM 修复并重试（最多 3 次）
    6. LLM 生成自然语言答案
    """
    try:
        logger.info(f"收到查询请求: {request.question}")

        # 运行 Agent 工作流
        result = await agent_graph.run(request.question)

        # 构造响应（兼容 answer 为 None 的情况，即重试耗尽）
        response = QueryResponse(
            question=result["question"],
            sql=result.get("validated_sql") or result.get("generated_sql") or "",
            is_sql_safe=result.get("is_sql_safe", False),
            columns=result.get("query_result", {}).get("columns", []),
            rows=result.get("query_result", {}).get("rows", []),
            answer=result.get("answer") or "抱歉，处理您的问题时遇到困难，请尝试换个问法。",
            execution_time_ms=result.get("query_result", {}).get("execution_time_ms", 0),
            retry_count=result.get("retry_count", 0),
            optimization_suggestions=result.get("optimization_suggestions", [])
        )

        return SuccessResponse(
            code=200,
            message="success",
            data=response
        )

    except Exception as e:
        logger.error(f"查询处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
