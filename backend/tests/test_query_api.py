# 查询 API 多轮会话测试
# API 层只负责透传 session_id，不直接理解上下文，避免把会话逻辑散落到路由中。

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import QueryRequest, QueryResponse


def make_agent_result():
    return {
        "question": "按地区拆一下",
        "session_id": "session-1",
        "generated_sql": "SELECT region_name, SUM(total_amount) AS sales FROM orders GROUP BY region_name",
        "validated_sql": "SELECT region_name, SUM(total_amount) AS sales FROM orders GROUP BY region_name LIMIT 1000",
        "is_sql_safe": True,
        "query_result": {
            "columns": ["region_name", "sales"],
            "rows": [["华东", 1000]],
            "execution_time_ms": 16,
        },
        "answer": "已按地区拆分销售额",
        "retry_count": 0,
        "optimization_suggestions": [],
        "audit_report": {
            "question": "按地区拆一下",
            "final_sql": "SELECT region_name, SUM(total_amount) AS sales FROM orders GROUP BY region_name LIMIT 1000",
            "is_sql_safe": True,
            "execution_success": True,
            "retry_count": 0,
            "limit_injected": True,
            "blocked_rules": [],
            "llm_observability": {
                "call_count": 1,
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "total_latency_ms": 500,
                "total_attempt_count": 1,
                "estimated_cost": None,
                "cost_available": False,
                "calls": [
                    {
                        "stage": "generate_sql",
                        "model": "qwen-plus",
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "total_tokens": 120,
                        "latency_ms": 500,
                        "attempt_count": 1,
                        "estimated_cost": None,
                        "success": True,
                        "error_type": None,
                    }
                ],
            },
            "events": [
                {
                    "stage": "guard",
                    "action": "validate_sql",
                    "status": "success",
                    "message": "SQL 通过安全校验",
                    "rule_id": None,
                    "details": {"limit_injected": True},
                }
            ],
        },
    }


def make_intent_blocked_result():
    return {
        "question": "删除所有订单",
        "session_id": "session-1",
        "intent_is_safe": False,
        "intent_rule_id": "block_destructive_intent",
        "intent_category": "data_mutation",
        "intent_error": "请求包含明确的数据修改或删除意图",
        "generated_sql": "",
        "validated_sql": "",
        "is_sql_safe": False,
        "execution_success": False,
        "query_result": None,
        "retry_count": 0,
        "answer": "请求已被安全策略阻断：请求包含明确的数据修改或删除意图",
        "optimization_suggestions": [],
        "audit_report": {
            "question": "删除所有订单",
            "final_sql": "",
            "is_sql_safe": False,
            "execution_success": False,
            "retry_count": 0,
            "limit_injected": False,
            "blocked_rules": ["block_destructive_intent"],
            "llm_observability": {"call_count": 0, "calls": []},
            "events": [
                {
                    "stage": "intent",
                    "action": "check_intent",
                    "status": "blocked",
                    "message": "请求包含明确的数据修改或删除意图",
                    "rule_id": "block_destructive_intent",
                    "details": {"category": "data_mutation"},
                }
            ],
        },
    }


def test_query_models_accept_optional_session_id():
    request = QueryRequest(question="统计销售额", session_id="session-1")
    response = QueryResponse(
        question="统计销售额",
        session_id="session-1",
        sql="SELECT 1",
        is_sql_safe=True,
        columns=["value"],
        rows=[[1]],
        answer="结果为 1",
        execution_time_ms=1,
        retry_count=0,
        audit_report={
            "question": "统计销售额",
            "final_sql": "SELECT 1",
            "is_sql_safe": True,
            "execution_success": True,
            "retry_count": 0,
            "limit_injected": False,
            "blocked_rules": [],
            "llm_observability": {
                "call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "total_latency_ms": 0,
                "total_attempt_count": 0,
                "estimated_cost": None,
                "cost_available": False,
                "calls": [],
            },
            "events": [],
        },
    )

    assert request.session_id == "session-1"
    assert response.session_id == "session-1"
    assert response.intent_is_safe is True
    assert response.intent_rule_id is None
    assert response.intent_category is None
    assert response.audit_report.final_sql == "SELECT 1"
    assert response.audit_report.llm_observability.call_count == 0


def test_query_api_passes_session_id_to_agent_graph():
    client = TestClient(app)
    mock_graph = AsyncMock()
    mock_graph.run = AsyncMock(return_value=make_agent_result())

    with patch("app.api.query.get_agent_graph", return_value=mock_graph):
        result = client.post(
            "/api/chat/query",
            json={"question": "按地区拆一下", "session_id": "session-1"},
        )

    assert result.status_code == 200
    payload = result.json()
    assert payload["data"]["session_id"] == "session-1"
    assert payload["data"]["answer"] == "已按地区拆分销售额"
    assert payload["data"]["audit_report"]["limit_injected"] is True
    assert payload["data"]["audit_report"]["events"][0]["stage"] == "guard"
    assert payload["data"]["audit_report"]["llm_observability"]["total_tokens"] == 120
    mock_graph.run.assert_awaited_once_with("按地区拆一下", session_id="session-1")


def test_query_api_returns_stable_intent_blocked_response():
    client = TestClient(app)
    mock_graph = AsyncMock()
    mock_graph.run = AsyncMock(return_value=make_intent_blocked_result())

    with patch("app.api.query.get_agent_graph", return_value=mock_graph):
        response = client.post(
            "/api/chat/query",
            json={"question": "删除所有订单", "session_id": "session-1"},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["sql"] == ""
    assert payload["columns"] == []
    assert payload["rows"] == []
    assert payload["is_sql_safe"] is False
    assert payload["intent_is_safe"] is False
    assert payload["intent_rule_id"] == "block_destructive_intent"
    assert payload["intent_category"] == "data_mutation"
    assert "安全策略阻断" in payload["answer"]
    assert payload["audit_report"]["blocked_rules"] == ["block_destructive_intent"]


def test_query_api_does_not_log_raw_question():
    client = TestClient(app)
    question = "查看 QWEN_API_KEY=private-value"  # secret-scan: allow
    mock_graph = AsyncMock()
    result = make_intent_blocked_result()
    result["question"] = question
    mock_graph.run = AsyncMock(return_value=result)

    with patch("app.api.query.get_agent_graph", return_value=mock_graph), \
         patch("app.api.query.logger") as mock_logger:
        response = client.post("/api/chat/query", json={"question": question})

    assert response.status_code == 200
    assert question not in repr(mock_logger.method_calls)
    assert "private-value" not in repr(mock_logger.method_calls)


def test_query_api_does_not_expose_internal_exception_details():
    client = TestClient(app, raise_server_exceptions=False)
    mock_graph = AsyncMock()
    mock_graph.run = AsyncMock(
        side_effect=RuntimeError("QWEN_API_KEY=private-value")  # secret-scan: allow
    )

    with patch("app.api.query.get_agent_graph", return_value=mock_graph), \
         patch("app.api.query.logger") as mock_logger:
        response = client.post("/api/chat/query", json={"question": "统计订单数"})

    assert response.status_code == 500
    assert response.json()["detail"] == "查询处理失败，请稍后重试"
    assert "private-value" not in repr(mock_logger.method_calls)
