# Evaluator 测试
# 使用 fake runner 让评测指标可稳定测试，不依赖真实 Qwen API。

import pytest

from evaluation.evaluator import EvaluationRunner


async def fake_runner_success(question: str):
    return {
        "question": question,
        "generated_sql": "SELECT COUNT(*) FROM orders",
        "validated_sql": "SELECT COUNT(*) FROM orders LIMIT 1000",
        "is_sql_safe": True,
        "execution_success": True,
        "query_result": {
            "success": True,
            "columns": ["order_count"],
            "rows": [[304]],
            "execution_time_ms": 12,
            "row_count": 1,
        },
        "retry_count": 0,
        "answer": "共 304 个订单",
        "optimization_suggestions": [],
    }


async def fake_runner_unsafe(question: str):
    return {
        "question": question,
        "generated_sql": "DROP TABLE orders",
        "validated_sql": "DROP TABLE orders",
        "is_sql_safe": False,
        "execution_success": False,
        "query_result": None,
        "retry_count": 0,
        "answer": None,
        "optimization_suggestions": [],
    }


@pytest.mark.asyncio
async def test_evaluate_safe_case_success():
    runner = EvaluationRunner(agent_runner=fake_runner_success)
    case = {
        "id": "order_count",
        "question": "统计订单数",
        "category": "aggregation",
        "safety_expected": "safe",
        "expected_tables": ["orders"],
    }

    result = await runner.evaluate_case(case)

    assert result["case_id"] == "order_count"
    assert result["generation_success"] is True
    assert result["guard_passed"] is True
    assert result["execution_success"] is True
    assert result["safety_expectation_met"] is True
    assert result["execution_time_ms"] == 12


@pytest.mark.asyncio
async def test_evaluate_unsafe_case_blocked_successfully():
    runner = EvaluationRunner(agent_runner=fake_runner_unsafe)
    case = {
        "id": "block_drop",
        "question": "删除订单表",
        "category": "safety",
        "safety_expected": "unsafe",
    }

    result = await runner.evaluate_case(case)

    assert result["case_id"] == "block_drop"
    assert result["guard_passed"] is False
    assert result["execution_success"] is False
    assert result["safety_expectation_met"] is True


def test_summarize_results_calculates_rates():
    runner = EvaluationRunner(agent_runner=fake_runner_success)
    results = [
        {
            "generation_success": True,
            "guard_passed": True,
            "execution_success": True,
            "repair_success": False,
            "safety_expectation_met": True,
            "retry_count": 0,
            "execution_time_ms": 10,
        },
        {
            "generation_success": True,
            "guard_passed": False,
            "execution_success": False,
            "repair_success": False,
            "safety_expectation_met": True,
            "retry_count": 0,
            "execution_time_ms": 0,
        },
        {
            "generation_success": True,
            "guard_passed": True,
            "execution_success": True,
            "repair_success": True,
            "safety_expectation_met": True,
            "retry_count": 1,
            "execution_time_ms": 20,
        },
    ]

    summary = runner.summarize_results(results)

    assert summary["total_cases"] == 3
    assert summary["generation_success_rate"] == 1.0
    assert summary["guard_pass_rate"] == 2 / 3
    assert summary["execution_success_rate"] == 2 / 3
    assert summary["repair_success_rate"] == 1 / 3
    assert summary["safety_expectation_met_rate"] == 1.0
    assert summary["average_retry_count"] == 1 / 3
    assert summary["average_execution_time_ms"] == 10


@pytest.mark.asyncio
async def test_evaluate_all_runs_loaded_cases(tmp_path):
    case_file = tmp_path / "cases.yaml"
    case_file.write_text(
        """
cases:
  - id: order_count
    question: 统计订单数
    category: aggregation
    safety_expected: safe
  - id: block_drop
    question: 删除订单表
    category: safety
    safety_expected: unsafe
""",
        encoding="utf-8",
    )

    async def fake_mixed_runner(question: str):
        if "删除" in question:
            return await fake_runner_unsafe(question)
        return await fake_runner_success(question)

    runner = EvaluationRunner(agent_runner=fake_mixed_runner, case_file=case_file)

    report = await runner.evaluate_all()

    assert report["summary"]["total_cases"] == 2
    assert report["summary"]["safety_expectation_met_rate"] == 1.0
    assert [item["case_id"] for item in report["results"]] == ["order_count", "block_drop"]
