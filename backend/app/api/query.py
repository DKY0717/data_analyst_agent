# 查询 API 模块
# 提供 /api/chat/query 端点，是整个系统的核心入口
# 接收自然语言问题，调用 AgentGraph 工作流，返回完整的分析结果

import json
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from ..models.schemas import QueryRequest, QueryResponse, SuccessResponse
from ..agents.graph import get_agent_graph
from ..services.query_cache import query_cache
from ..security.rate_limit import limiter, RATE_LIMIT_QUERY
from ..utils.logger import logger

router = APIRouter()


@router.post("/api/chat/query", response_model=SuccessResponse)
@limiter.limit(RATE_LIMIT_QUERY)
async def query(request: Request, body: QueryRequest):
    """处理自然语言查询，返回 SQL、查询结果和自然语言解释

    完整流程:
    0. 检查缓存（命中则直接返回）
    1. AgentGraph 加载 Schema
    2. LLM 生成 SQL
    3. SQL Guard 安全校验
    4. 执行 SQL 查询
    5. 如失败则 LLM 修复并重试（最多 3 次）
    6. LLM 生成自然语言答案
    7. 写入缓存
    """
    try:
        logger.info("收到查询请求")

        # 跳过缓存的场景：有澄清响应、有 session_id（多轮追问上下文不同）
        if not body.clarification_id and not body.session_id:
            cached = query_cache.get(body.question)
            if cached:
                logger.info("缓存命中，直接返回")
                return SuccessResponse(code=200, message="success (cached)", data=cached)

        clarification_response = None
        if body.clarification_id:
            clarification_response = {
                "clarification_id": body.clarification_id,
                "candidate_id": body.clarification_candidate_id,
                "text": body.clarification_text,
            }

        # session_id 和澄清回答只做透传；上下文恢复由 AgentGraph 和 SessionStore 统一管理。
        result = await get_agent_graph().run(
            body.question,
            session_id=body.session_id,
            clarification_response=clarification_response,
        )

        # 阻断请求没有查询结果，统一归一为空对象以保持稳定的 HTTP 200 响应。
        query_result = result.get("query_result") or {}

        # 构造响应（兼容 answer 为 None 的情况，即重试耗尽）
        response = QueryResponse(
            question=result["question"],
            session_id=result.get("session_id") or body.session_id,
            status=result.get("status", "completed"),
            intent_is_safe=result.get("intent_is_safe", True),
            intent_rule_id=result.get("intent_rule_id"),
            intent_category=result.get("intent_category"),
            sql=result.get("validated_sql") or result.get("generated_sql") or "",
            is_sql_safe=result.get("is_sql_safe", False),
            columns=query_result.get("columns", []),
            rows=query_result.get("rows", []),
            answer=result.get("answer") or "抱歉，处理您的问题时遇到困难，请尝试换个问法。",
            execution_time_ms=query_result.get("execution_time_ms", 0),
            retry_count=result.get("retry_count", 0),
            optimization_suggestions=result.get("optimization_suggestions", []),
            analysis_intent=result.get("analysis_intent"),
            clarification=result.get("clarification_request"),
            audit_report=result.get("audit_report"),
        )

        # 成功且无 session_id 时写入缓存
        if not body.session_id and result.get("execution_success"):
            query_cache.put(body.question, response.model_dump())

        return SuccessResponse(
            code=200,
            message="success",
            data=response
        )

    except Exception:
        # 异常原文可能包含凭据、SQL 或数据库细节，只记录稳定消息并返回通用错误。
        logger.error("查询处理失败")
        raise HTTPException(status_code=500, detail="查询处理失败，请稍后重试")


@router.post("/api/chat/query/stream")
@limiter.limit(RATE_LIMIT_QUERY)
async def query_stream(request: Request, body: QueryRequest):
    """SSE 流式查询端点，实时推送处理进度和部分结果"""
    progress_queue: asyncio.Queue = asyncio.Queue()

    def on_progress_callback(stage: str, progress: int):
        progress_queue.put_nowait({"stage": stage, "progress": progress})

    async def run_pipeline():
        try:
            clarification_response = None
            if body.clarification_id:
                clarification_response = {
                    "clarification_id": body.clarification_id,
                    "candidate_id": body.clarification_candidate_id,
                    "text": body.clarification_text,
                }
            result = await get_agent_graph().run(
                body.question,
                session_id=body.session_id,
                clarification_response=clarification_response,
                on_progress=on_progress_callback,
            )
            await progress_queue.put({"type": "done", "result": result})
        except Exception as e:
            await progress_queue.put({"type": "error", "message": str(e)})

    async def event_generator():
        task = asyncio.create_task(run_pipeline())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    if task.done():
                        break
                    continue

                if event.get("type") == "done":
                    result = event["result"]
                    query_result = result.get("query_result") or {}
                    response = QueryResponse(
                        question=result["question"],
                        session_id=result.get("session_id") or body.session_id,
                        status=result.get("status", "completed"),
                        intent_is_safe=result.get("intent_is_safe", True),
                        intent_rule_id=result.get("intent_rule_id"),
                        intent_category=result.get("intent_category"),
                        sql=result.get("validated_sql") or result.get("generated_sql") or "",
                        is_sql_safe=result.get("is_sql_safe", False),
                        columns=query_result.get("columns", []),
                        rows=query_result.get("rows", []),
                        answer=result.get("answer") or "抱歉，处理您的问题时遇到困难，请尝试换个问法。",
                        execution_time_ms=query_result.get("execution_time_ms", 0),
                        retry_count=result.get("retry_count", 0),
                        optimization_suggestions=result.get("optimization_suggestions", []),
                        analysis_intent=result.get("analysis_intent"),
                        clarification=result.get("clarification_request"),
                        audit_report=result.get("audit_report"),
                    )
                    if not body.session_id and result.get("execution_success"):
                        query_cache.put(body.question, response.model_dump())
                    yield f"data: {json.dumps({'type': 'result', 'data': response.model_dump()}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    break
                elif event.get("type") == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': '查询处理失败，请稍后重试'}, ensure_ascii=False)}\n\n"
                    break
                else:
                    yield f"data: {json.dumps({'type': 'progress', 'stage': event['stage'], 'progress': event['progress']}, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
