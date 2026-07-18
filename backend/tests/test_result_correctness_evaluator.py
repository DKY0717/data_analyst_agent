"""结果正确性评测器的确定性测试。"""

import json
from pathlib import Path

import pytest

from evaluation.result_correctness_evaluator import (
    ResultCorrectnessEvaluator,
    parse_args,
)
from evaluation.shard_support import ShardSpec, resolve_shard_cli_options


def sample_case(case_id="monthly_sales_2024"):
    """构造最小黄金 case，测试不依赖真实数据库或 Qwen。"""
    return {
        "id": case_id,
        "question": "统计 2024 年每个月的销售额",
        "category": "time_series",
        "reference_sql": "SELECT '2024-01' AS month, 10 AS sales_amount",
        "comparison": {
            "mode": "ordered",
            "required_columns": ["month", "sales_amount"],
            "order_by": ["month"],
            "absolute_tolerance": 0.001,
        },
        "fixed_assertions": {"row_count": 1},
    }


async def successful_agent(question):
    return {
        "validated_sql": "SELECT '2024-01' AS month, 10 AS sales_amount",
        "execution_success": True,
        "query_result": {
            "columns": ["month", "sales_amount"],
            "rows": [["2024-01", 10]],
        },
    }


class FakeReferenceRunner:
    def __init__(self, result=None):
        self.result = result or {
            "guard_passed": True,
            "execution_success": True,
            "columns": ["month", "sales_amount"],
            "rows": [["2024-01", 10]],
            "error_type": None,
        }

    def run(self, reference_sql):
        return self.result


class FakeComparator:
    def __init__(self, result=None, error=None):
        self.result = result or {
            "columns_matched": True,
            "row_count_matched": True,
            "values_matched": True,
            "order_matched": True,
            "fixed_assertions_matched": True,
            "result_correct": True,
            "failure_types": [],
            "diff_samples": [],
        }
        self.error = error

    def compare(self, **kwargs):
        if self.error:
            raise self.error
        return self.result


@pytest.mark.asyncio
async def test_evaluate_case_compares_agent_and_reference_results():
    runner = ResultCorrectnessEvaluator(
        agent_runner=successful_agent,
        reference_runner=FakeReferenceRunner(),
        comparator=FakeComparator(),
    )

    result = await runner.evaluate_case(sample_case())

    assert result["case_id"] == "monthly_sales_2024"
    assert result["agent_execution_success"] is True
    assert result["reference_guard_passed"] is True
    assert result["reference_execution_success"] is True
    assert result["result_correct"] is True
    assert result["failure_type"] is None
    assert result["agent_sql"]
    assert "query_result" not in result
    assert "rows" not in result


@pytest.mark.asyncio
async def test_agent_execution_failure_returns_stable_result():
    async def failed_agent(question):
        return {
            "generated_sql": "SELECT missing FROM orders",
            "execution_success": False,
        }

    runner = ResultCorrectnessEvaluator(
        agent_runner=failed_agent,
        reference_runner=FakeReferenceRunner(),
        comparator=FakeComparator(),
    )

    result = await runner.evaluate_case(sample_case())

    assert result["failure_type"] == "agent_execution_failed"
    assert result["result_correct"] is False
    assert result["reference_guard_passed"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reference_result", "failure_type"),
    [
        (
            {
                "guard_passed": False,
                "execution_success": False,
                "error_type": "reference_guard_blocked",
            },
            "reference_guard_blocked",
        ),
        (
            {
                "guard_passed": True,
                "execution_success": False,
                "error_type": "reference_execution_failed",
            },
            "reference_execution_failed",
        ),
    ],
)
async def test_reference_failures_return_stable_result(reference_result, failure_type):
    runner = ResultCorrectnessEvaluator(
        agent_runner=successful_agent,
        reference_runner=FakeReferenceRunner(reference_result),
        comparator=FakeComparator(),
    )

    result = await runner.evaluate_case(sample_case())

    assert result["failure_type"] == failure_type
    assert result["result_correct"] is False


@pytest.mark.asyncio
async def test_comparator_exception_returns_unexpected_error():
    runner = ResultCorrectnessEvaluator(
        agent_runner=successful_agent,
        reference_runner=FakeReferenceRunner(),
        comparator=FakeComparator(error=RuntimeError("secret database detail")),
    )

    result = await runner.evaluate_case(sample_case())

    assert result["failure_type"] == "unexpected_error"
    assert result["result_correct"] is False
    assert "secret database detail" not in str(result)


@pytest.mark.asyncio
async def test_evaluate_all_continues_after_single_case_failure(tmp_path):
    case_file = tmp_path / "cases.yaml"
    case_file.write_text(
        """
cases:
  - id: broken
    question: broken
    category: aggregation
    reference_sql: SELECT 1 AS value
    comparison:
      mode: scalar
      required_columns: [value]
  - id: good
    question: good
    category: aggregation
    reference_sql: SELECT 1 AS value
    comparison:
      mode: scalar
      required_columns: [value]
""",
        encoding="utf-8",
    )

    async def mixed_agent(question):
        if question == "broken":
            raise RuntimeError("agent failure")
        return {
            "validated_sql": "SELECT 1 AS value",
            "execution_success": True,
            "query_result": {"columns": ["value"], "rows": [[1]]},
        }

    runner = ResultCorrectnessEvaluator(
        agent_runner=mixed_agent,
        reference_runner=FakeReferenceRunner(
            {
                "guard_passed": True,
                "execution_success": True,
                "columns": ["value"],
                "rows": [[1]],
            }
        ),
        comparator=FakeComparator(),
        case_file=case_file,
    )

    report = await runner.evaluate_all()

    assert [item["case_id"] for item in report["results"]] == ["broken", "good"]
    assert report["results"][0]["failure_type"] == "unexpected_error"
    assert report["results"][1]["result_correct"] is True


def test_summarize_results_calculates_correctness_rates():
    runner = ResultCorrectnessEvaluator(
        agent_runner=successful_agent,
        reference_runner=FakeReferenceRunner(),
        comparator=FakeComparator(),
    )
    results = [
        {
            "category": "business_metric",
            "agent_execution_success": True,
            "reference_guard_passed": True,
            "reference_execution_success": True,
            "columns_matched": True,
            "values_matched": True,
            "order_matched": True,
            "fixed_assertions_matched": True,
            "result_correct": True,
        },
        {
            "category": "business_metric",
            "agent_execution_success": True,
            "reference_guard_passed": True,
            "reference_execution_success": True,
            "columns_matched": True,
            "values_matched": False,
            "order_matched": False,
            "fixed_assertions_matched": True,
            "result_correct": False,
        },
        {
            "category": "dimension",
            "agent_execution_success": True,
            "reference_guard_passed": True,
            "reference_execution_success": True,
            "columns_matched": False,
            "values_matched": False,
            "order_matched": True,
            "fixed_assertions_matched": True,
            "result_correct": False,
        },
        {
            "category": "dimension",
            "agent_execution_success": False,
            "reference_guard_passed": False,
            "reference_execution_success": False,
            "columns_matched": False,
            "values_matched": False,
            "order_matched": False,
            "fixed_assertions_matched": False,
            "result_correct": False,
        },
    ]

    summary = runner.summarize_results(results)

    assert summary["total_cases"] == 4
    assert summary["result_correctness_rate"] == 0.25
    assert summary["column_match_rate"] == 0.5
    assert summary["value_match_rate"] == 0.25
    assert summary["order_match_rate"] == 0.5
    assert summary["business_metric_accuracy"] == 0.5
    assert summary["reference_guard_pass_rate"] == 0.75
    assert summary["reference_execution_success_rate"] == 0.75
    assert summary["fixed_assertion_pass_rate"] == 0.75


def test_summarize_empty_results_returns_zero_rates():
    runner = ResultCorrectnessEvaluator(
        agent_runner=successful_agent,
        reference_runner=FakeReferenceRunner(),
        comparator=FakeComparator(),
    )

    summary = runner.summarize_results([])

    assert summary["total_cases"] == 0
    assert all(value == 0 for key, value in summary.items() if key != "total_cases")


def test_load_cases_uses_configured_file(tmp_path):
    case_file = Path(tmp_path) / "cases.yaml"
    case_file.write_text("cases: []\n", encoding="utf-8")
    runner = ResultCorrectnessEvaluator(
        agent_runner=successful_agent,
        reference_runner=FakeReferenceRunner(),
        comparator=FakeComparator(),
        case_file=case_file,
    )

    assert runner.load_cases() == []


@pytest.mark.asyncio
async def test_correctness_evaluate_all_runs_selected_shard_and_writes_checkpoint(
    monkeypatch, tmp_path
):
    case_file = tmp_path / "golden_cases.yaml"
    cases = [sample_case(f"golden_{index}") for index in range(4)]
    case_file.write_text(
        "cases:\n"
        + "".join(
            f"  - id: {case['id']}\n"
            "    question: test\n"
            "    category: time_series\n"
            "    reference_sql: SELECT 1\n"
            "    comparison: {mode: scalar}\n"
            for case in cases
        ),
        encoding="utf-8",
    )
    runner = ResultCorrectnessEvaluator(
        agent_runner=successful_agent,
        reference_runner=FakeReferenceRunner(),
        comparator=FakeComparator(),
        case_file=case_file,
    )
    calls = []

    async def fake_evaluate_case(case):
        calls.append(case["id"])
        return runner._base_result(case)

    monkeypatch.setattr(runner, "evaluate_case", fake_evaluate_case)
    checkpoint = tmp_path / "correctness-shard.json"

    report = await runner.evaluate_all(
        shard=ShardSpec(index=1, count=2),
        checkpoint_output=checkpoint,
        head_sha="abc123",
        provider="mimo",
        model="mimo-v2.5-pro",
    )

    assert calls == ["golden_1", "golden_3"]
    assert json.loads(checkpoint.read_text(encoding="utf-8")) == report
    assert report["shard"]["complete"] is True


def test_correctness_cli_exposes_shared_shard_contract():
    args = parse_args(
        [
            "--case-file",
            "cases.yaml",
            "--shard-index",
            "0",
            "--shard-count",
            "5",
            "--checkpoint-output",
            "checkpoint.json",
        ]
    )

    assert resolve_shard_cli_options(args).shard == ShardSpec(index=0, count=5)
