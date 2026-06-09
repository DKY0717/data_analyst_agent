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
            "events": [],
        },
    )

    assert request.session_id == "session-1"
    assert response.session_id == "session-1"
    assert response.audit_report.final_sql == "SELECT 1"


def test_query_api_passes_session_id_to_agent_graph():
    client = TestClient(app)

    with patch("app.api.query.agent_graph") as mock_graph:
        mock_graph.run = AsyncMock(return_value=make_agent_result())

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
    mock_graph.run.assert_awaited_once_with("按地区拆一下", session_id="session-1")
