# SQL Repair 故障注入评测器测试
# 使用 fake 依赖稳定覆盖安全前置校验、修复、执行、意图保持和汇总指标。

import json

import pytest

from app.models.schemas import SQLRepairOutput
from app.services.llm_observability import record_call
from evaluation.repair_evaluator import RepairEvaluationRunner, parse_args
from evaluation.shard_support import ShardSpec, resolve_shard_cli_options


CASE = {
    "id": "wrong_column",
    "description": "修复错误字段",
    "original_sql": "SELECT SUM(revenue) FROM orders",
    "expected_tables": ["orders"],
    "required_sql_fragments": ["total_amount"],
    "forbidden_sql_fragments": ["revenue"],
}


class FakeGuard:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def validate(self, sql):
        self.calls.append(sql)
        return next(self.results)


class FakeQueryRunner:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def execute(self, sql):
        self.calls.append(sql)
        return next(self.results)


class FakeRepairAgent:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.calls = []

    async def repair(self, original_sql, error_message, schema_context):
        self.calls.append((original_sql, error_message, schema_context))
        if self.error:
            raise self.error
        return self.output


def safe(sql):
    return {"is_safe": True, "sanitized_sql": sql, "reason": None}


def blocked(sql, reason="blocked"):
    return {"is_safe": False, "sanitized_sql": sql, "reason": reason}


def failed(error="database error"):
    return {"success": False, "error": error, "execution_time_ms": 2}


def succeeded():
    return {"success": True, "columns": ["sales"], "rows": [[100]], "row_count": 1, "execution_time_ms": 5}


def make_runner(guard_results, query_results, repair_output=None, repair_error=None):
    guard = FakeGuard(guard_results)
    query_runner = FakeQueryRunner(query_results)
    repair_agent = FakeRepairAgent(repair_output, repair_error)
    runner = RepairEvaluationRunner(
        guard=guard,
        query_runner=query_runner,
        repair_agent=repair_agent,
        schema_loader=lambda: {"tables": {"orders": {}}},
    )
    return runner, guard, query_runner, repair_agent


@pytest.mark.asyncio
async def test_evaluate_case_runs_full_repair_pipeline():
    repair_output = SQLRepairOutput(
        repaired_sql="SELECT SUM(total_amount) FROM orders",
        repair_reason="revenue 字段不存在，改用 total_amount",
    )
    runner, guard, query_runner, repair_agent = make_runner(
        [safe(CASE["original_sql"]), safe(repair_output.repaired_sql)],
        [failed("column revenue not found"), succeeded()],
        repair_output=repair_output,
    )

    result = await runner.evaluate_case(CASE)

    assert result["failure_injected"] is True
    assert result["repair_output_success"] is True
    assert result["repaired_guard_passed"] is True
    assert result["execution_success"] is True
    assert result["intent_preserved"] is True
    assert result["end_to_end_success"] is True
    assert len(guard.calls) == 2
    assert len(query_runner.calls) == 2
    assert repair_agent.calls[0][1] == "column revenue not found"


@pytest.mark.asyncio
async def test_original_guard_failure_skips_execution_and_repair():
    runner, _, query_runner, repair_agent = make_runner(
        [blocked(CASE["original_sql"])],
        [],
    )

    result = await runner.evaluate_case(CASE)

    assert result["original_guard_passed"] is False
    assert result["failure_injected"] is False
    assert result["error"] == "blocked"
    assert query_runner.calls == []
    assert repair_agent.calls == []


@pytest.mark.asyncio
async def test_original_sql_unexpected_success_skips_repair():
    runner, _, _, repair_agent = make_runner(
        [safe(CASE["original_sql"])],
        [succeeded()],
    )

    result = await runner.evaluate_case(CASE)

    assert result["failure_injected"] is False
    assert "错误 SQL 意外执行成功" in result["error"]
    assert repair_agent.calls == []


@pytest.mark.asyncio
async def test_repair_exception_is_recorded_without_raising():
    runner, _, _, _ = make_runner(
        [safe(CASE["original_sql"])],
        [failed()],
        repair_error=RuntimeError("qwen unavailable"),
    )

    result = await runner.evaluate_case(CASE)

    assert result["repair_output_success"] is False
    assert result["error"] == "qwen unavailable"


@pytest.mark.asyncio
async def test_repaired_guard_failure_skips_second_execution():
    repair_output = SQLRepairOutput(repaired_sql="DROP TABLE orders", repair_reason="bad repair")
    runner, _, query_runner, _ = make_runner(
        [safe(CASE["original_sql"]), blocked(repair_output.repaired_sql, "禁止 DROP")],
        [failed()],
        repair_output=repair_output,
    )

    result = await runner.evaluate_case(CASE)

    assert result["repaired_guard_passed"] is False
    assert result["execution_success"] is False
    assert result["error"] == "禁止 DROP"
    assert len(query_runner.calls) == 1


def test_check_intent_requires_tables_required_fragments_and_forbidden_absence():
    runner, _, _, _ = make_runner([], [])

    preserved = runner.check_intent(
        "SELECT SUM(total_amount) FROM orders",
        CASE,
    )
    drifted = runner.check_intent(
        "SELECT SUM(revenue) FROM orders",
        CASE,
    )

    assert preserved == {
        "expected_tables_met": True,
        "required_fragments_met": True,
        "forbidden_fragments_absent": True,
        "intent_preserved": True,
    }
    assert drifted["intent_preserved"] is False
    assert drifted["required_fragments_met"] is False
    assert drifted["forbidden_fragments_absent"] is False


def test_summarize_results_calculates_repair_metrics():
    runner, _, _, _ = make_runner([], [])
    results = [
        {
            "failure_injected": True,
            "repair_output_success": True,
            "repaired_guard_passed": True,
            "execution_success": True,
            "intent_preserved": True,
            "end_to_end_success": True,
            "execution_time_ms": 10,
            "llm_call_count": 1,
            "llm_total_tokens": 500,
            "llm_latency_ms": 800,
            "llm_estimated_cost": 0.001,
            "llm_cost_available": True,
        },
        {
            "failure_injected": True,
            "repair_output_success": True,
            "repaired_guard_passed": False,
            "execution_success": False,
            "intent_preserved": False,
            "end_to_end_success": False,
            "execution_time_ms": 0,
            "llm_call_count": 1,
            "llm_total_tokens": 700,
            "llm_latency_ms": 1000,
            "llm_estimated_cost": 0.002,
            "llm_cost_available": True,
        },
    ]

    summary = runner.summarize_results(results)

    assert summary["total_cases"] == 2
    assert summary["failure_injection_rate"] == 1.0
    assert summary["repair_output_success_rate"] == 1.0
    assert summary["repaired_guard_pass_rate"] == 0.5
    assert summary["repair_execution_success_rate"] == 0.5
    assert summary["intent_preservation_rate"] == 0.5
    assert summary["end_to_end_repair_success_rate"] == 0.5
    assert summary["average_execution_time_ms"] == 5
    assert summary["average_llm_call_count"] == 1
    assert summary["average_llm_total_tokens"] == 600
    assert summary["average_llm_latency_ms"] == 900
    assert summary["total_llm_estimated_cost"] == pytest.approx(0.003)
    assert summary["cost_available"] is True


@pytest.mark.asyncio
async def test_each_repair_case_uses_independent_llm_trace():
    class MetricsRepairAgent:
        async def repair(self, original_sql, error_message, schema_context):
            tokens = 300 if "revenue" in original_sql else 600
            record_call(
                {
                    "stage": "repair_sql",
                    "model": "qwen-plus",
                    "input_tokens": tokens - 100,
                    "output_tokens": 100,
                    "total_tokens": tokens,
                    "latency_ms": 500,
                    "attempt_count": 1,
                    "estimated_cost": None,
                    "success": True,
                    "error_type": None,
                }
            )
            return SQLRepairOutput(
                repaired_sql="SELECT SUM(total_amount) FROM orders",
                repair_reason="修复字段",
            )

    runner = RepairEvaluationRunner(
        guard=FakeGuard(
            [
                safe("SELECT SUM(revenue) FROM orders"),
                safe("SELECT SUM(total_amount) FROM orders"),
                safe("SELECT SUM(bad_amount) FROM orders"),
                safe("SELECT SUM(total_amount) FROM orders"),
            ]
        ),
        query_runner=FakeQueryRunner([failed(), succeeded(), failed(), succeeded()]),
        repair_agent=MetricsRepairAgent(),
        schema_loader=lambda: {"tables": {"orders": {}}},
    )
    second_case = {
        **CASE,
        "id": "wrong_column_2",
        "original_sql": "SELECT SUM(bad_amount) FROM orders",
        "forbidden_sql_fragments": ["bad_amount"],
    }

    first = await runner.evaluate_case(CASE)
    second = await runner.evaluate_case(second_case)

    assert first["llm_total_tokens"] == 300
    assert second["llm_total_tokens"] == 600
    assert first["llm_call_count"] == second["llm_call_count"] == 1


@pytest.mark.asyncio
async def test_evaluate_all_records_unexpected_case_error_and_continues(tmp_path):
    """任一依赖意外抛异常时，整批评测仍应继续并返回稳定结果结构。"""
    case_file = tmp_path / "repair_cases.yaml"
    case_file.write_text(
        """
cases:
  - id: exploding_case
    description: 依赖异常
    original_sql: SELECT bad FROM orders
    expected_tables: [orders]
    required_sql_fragments: []
    forbidden_sql_fragments: []
  - id: blocked_case
    description: Guard 阻断
    original_sql: SELECT bad FROM orders
    expected_tables: [orders]
    required_sql_fragments: []
    forbidden_sql_fragments: []
""",
        encoding="utf-8",
    )

    class ExplodingThenBlockedGuard:
        def __init__(self):
            self.calls = 0

        def validate(self, sql):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("unexpected guard failure")
            return blocked(sql, "blocked")

    runner = RepairEvaluationRunner(
        guard=ExplodingThenBlockedGuard(),
        query_runner=FakeQueryRunner([]),
        repair_agent=FakeRepairAgent(),
        schema_loader=lambda: {"tables": {}},
        case_file=case_file,
    )

    report = await runner.evaluate_all()

    assert len(report["results"]) == 2
    assert report["results"][0]["error"] == "unexpected guard failure"
    assert report["results"][1]["error"] == "blocked"


@pytest.mark.asyncio
async def test_repair_evaluate_all_runs_only_selected_shard_and_writes_checkpoint(
    monkeypatch, tmp_path
):
    case_file = tmp_path / "repair_cases.yaml"
    case_file.write_text(
        """
cases:
  - {id: repair_0, description: d0, original_sql: SELECT 0}
  - {id: repair_1, description: d1, original_sql: SELECT 1}
  - {id: repair_2, description: d2, original_sql: SELECT 2}
  - {id: repair_3, description: d3, original_sql: SELECT 3}
""",
        encoding="utf-8",
    )
    runner = RepairEvaluationRunner(case_file=case_file)
    calls = []

    async def fake_evaluate_case(case):
        calls.append(case["id"])
        return {**runner._empty_result({**case, "description": case["description"]}), "case_id": case["id"]}

    monkeypatch.setattr(runner, "evaluate_case", fake_evaluate_case)
    checkpoint = tmp_path / "repair-shard.json"

    report = await runner.evaluate_all(
        shard=ShardSpec(index=0, count=2),
        checkpoint_output=checkpoint,
        head_sha="abc123",
        provider="mimo",
        model="mimo-v2.5-pro",
    )

    assert calls == ["repair_0", "repair_2"]
    assert json.loads(checkpoint.read_text(encoding="utf-8")) == report
    assert report["shard"]["complete"] is True


def test_repair_cli_exposes_shared_shard_contract():
    args = parse_args(
        [
            "--shard-index",
            "1",
            "--shard-count",
            "3",
            "--checkpoint-output",
            "checkpoint.json",
        ]
    )

    assert resolve_shard_cli_options(args).shard == ShardSpec(index=1, count=3)
