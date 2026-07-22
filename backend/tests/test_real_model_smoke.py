"""真实模型 smoke Runner 的确定性契约测试。"""

import pytest

from app.utils.exceptions import LLMResponseError
from evaluation.real_model_smoke import RealModelSmokeRunner, SMOKE_CASE_IDS


def completed_state(row_count=2):
    return {
        "status": "completed",
        "intent_is_safe": True,
        "is_sql_safe": True,
        "permission_allowed": True,
        "execution_success": True,
        "query_result": {"columns": ["label", "value"], "rows": [], "row_count": row_count},
        "audit_report": {"blocked_rules": []},
    }


@pytest.mark.asyncio
async def test_real_model_smoke_runs_four_high_value_cases_with_declared_roles():
    calls = []

    async def fake_agent(question, session_id=None, auth_user=None):
        calls.append((question, session_id, auth_user))
        if "客户姓名" in question:
            return {
                "status": "blocked",
                "intent_is_safe": True,
                "is_sql_safe": True,
                "permission_allowed": False,
                "execution_success": False,
                "query_result": None,
                "audit_report": {"blocked_rules": ["block_unauthorized_column"]},
            }
        return completed_state()

    report = await RealModelSmokeRunner(agent_runner=fake_agent).evaluate_all()

    assert report["summary"] == {
        "total_cases": 4,
        "passed_cases": 4,
        "passed": True,
    }
    assert [result["case_id"] for result in report["results"]] == list(SMOKE_CASE_IDS)
    assert {call[2]["roles"][0] for call in calls} == {"analyst", "admin"}
    assert all(call[1].startswith("real-smoke:") for call in calls)
    assert "sql" not in repr(report).lower()


@pytest.mark.asyncio
async def test_real_model_smoke_classifies_guard_failure_without_error_text():
    async def blocked_by_guard(*args, **kwargs):
        return {
            "status": "blocked",
            "intent_is_safe": True,
            "is_sql_safe": False,
            "permission_allowed": True,
            "execution_success": False,
            "query_result": None,
            "audit_report": {"blocked_rules": ["block_invalid_limit"]},
        }

    report = await RealModelSmokeRunner(agent_runner=blocked_by_guard).evaluate_all()

    assert report["summary"]["passed"] is False
    assert all(result["failure_stage"] == "sql_guard" for result in report["results"])
    assert all("error_type" not in result for result in report["results"])


@pytest.mark.asyncio
async def test_real_model_smoke_records_only_structured_provider_error_metadata():
    """真实 smoke 要能诊断供应商拒绝原因，但不得写入原始 message。"""
    async def provider_rejected(*args, **kwargs):
        raise LLMResponseError(
            "API 返回非 200 状态码: 400 (code=Arrearage)",
            status_code=400,
            provider_code="Arrearage",
            provider_type="invalid_request_error",
        )

    report = await RealModelSmokeRunner(agent_runner=provider_rejected).evaluate_all()

    assert report["summary"]["passed"] is False
    for result in report["results"]:
        assert result["error_type"] == "LLMResponseError"
        assert result["provider_status_code"] == 400
        assert result["provider_error_code"] == "Arrearage"
        assert result["provider_error_type"] == "invalid_request_error"
        assert "message" not in result
