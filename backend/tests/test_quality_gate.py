import json

import pytest

from evaluation.quality_gate import QualityGateError, evaluate_quality, main, to_markdown


def passing_summaries():
    return (
        {
            "safe_execution_success_rate": 1.0,
            "unsafe_block_rate": 1.0,
            "safety_expectation_met_rate": 1.0,
            "average_llm_call_count": 1.78,
            "average_llm_total_tokens": 1889.28,
            "average_llm_latency_ms": 9301,
        },
        {
            "end_to_end_repair_success_rate": 1.0,
            "average_llm_total_tokens": 875.67,
            "average_llm_latency_ms": 3862.5,
        },
    )


def test_evaluate_quality_passes_when_all_thresholds_are_met():
    nl2sql_summary, repair_summary = passing_summaries()

    result = evaluate_quality(nl2sql_summary, repair_summary)

    assert result["passed"] is True
    assert len(result["checks"]) == 4
    assert all(check["passed"] for check in result["checks"])


def test_evaluate_quality_rejects_old_31_of_32_safety_baseline():
    nl2sql_summary, repair_summary = passing_summaries()
    nl2sql_summary["unsafe_block_rate"] = 0.875
    nl2sql_summary["safety_expectation_met_rate"] = 31 / 32

    result = evaluate_quality(nl2sql_summary, repair_summary)

    assert result["passed"] is False
    assert [check["metric"] for check in result["checks"] if not check["passed"]] == [
        "unsafe_block_rate",
        "safety_expectation_met_rate",
    ]


@pytest.mark.parametrize(
    ("summary_name", "metric"),
    [
        ("nl2sql", "safe_execution_success_rate"),
        ("nl2sql", "unsafe_block_rate"),
        ("nl2sql", "safety_expectation_met_rate"),
        ("repair", "end_to_end_repair_success_rate"),
    ],
)
def test_evaluate_quality_fails_when_a_metric_drops_below_threshold(
    summary_name, metric
):
    nl2sql_summary, repair_summary = passing_summaries()
    target_summary = nl2sql_summary if summary_name == "nl2sql" else repair_summary
    target_summary[metric] -= 0.001

    result = evaluate_quality(nl2sql_summary, repair_summary)

    failed_checks = [check for check in result["checks"] if not check["passed"]]
    assert result["passed"] is False
    assert [check["metric"] for check in failed_checks] == [metric]


def test_evaluate_quality_rejects_missing_required_metric():
    nl2sql_summary, repair_summary = passing_summaries()
    del nl2sql_summary["unsafe_block_rate"]

    with pytest.raises(QualityGateError, match="unsafe_block_rate"):
        evaluate_quality(nl2sql_summary, repair_summary)


def test_evaluate_quality_rejects_non_numeric_required_metric():
    nl2sql_summary, repair_summary = passing_summaries()
    repair_summary["end_to_end_repair_success_rate"] = "100%"

    with pytest.raises(QualityGateError, match="end_to_end_repair_success_rate"):
        evaluate_quality(nl2sql_summary, repair_summary)


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf")])
def test_evaluate_quality_rejects_non_finite_required_metric(invalid_value):
    nl2sql_summary, repair_summary = passing_summaries()
    nl2sql_summary["safe_execution_success_rate"] = invalid_value

    with pytest.raises(QualityGateError, match="safe_execution_success_rate"):
        evaluate_quality(nl2sql_summary, repair_summary)


def test_display_metrics_default_to_zero_without_affecting_gate():
    nl2sql_summary, repair_summary = passing_summaries()
    for summary in (nl2sql_summary, repair_summary):
        summary.pop("average_llm_total_tokens", None)
        summary.pop("average_llm_latency_ms", None)

    result = evaluate_quality(nl2sql_summary, repair_summary)
    markdown = to_markdown(result, nl2sql_summary, repair_summary)

    assert result["passed"] is True
    assert "0.00" in markdown


def write_reports(tmp_path, *, below_threshold=False):
    nl2sql_summary, repair_summary = passing_summaries()
    if below_threshold:
        nl2sql_summary["unsafe_block_rate"] = 0.5

    nl2sql_path = tmp_path / "nl2sql.json"
    repair_path = tmp_path / "repair.json"
    nl2sql_path.write_text(
        json.dumps({"summary": nl2sql_summary}), encoding="utf-8"
    )
    repair_path.write_text(json.dumps({"summary": repair_summary}), encoding="utf-8")
    return nl2sql_path, repair_path


def test_main_writes_json_and_markdown_outputs(tmp_path):
    nl2sql_path, repair_path = write_reports(tmp_path)
    json_output = tmp_path / "quality-gate.json"
    markdown_output = tmp_path / "quality-gate.md"

    exit_code = main(
        [
            "--nl2sql-report",
            str(nl2sql_path),
            "--repair-report",
            str(repair_path),
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ]
    )

    assert exit_code == 0
    assert json.loads(json_output.read_text(encoding="utf-8"))["passed"] is True
    markdown = markdown_output.read_text(encoding="utf-8")
    assert "危险请求阻断率" in markdown
    assert "SQL Repair 端到端成功率" in markdown
    assert "平均 Token" in markdown
    assert "平均 LLM 耗时" in markdown


def test_main_warn_mode_returns_zero_when_gate_fails(tmp_path):
    nl2sql_path, repair_path = write_reports(tmp_path, below_threshold=True)
    json_output = tmp_path / "quality-gate.json"
    markdown_output = tmp_path / "quality-gate.md"

    exit_code = main(
        [
            "--nl2sql-report",
            str(nl2sql_path),
            "--repair-report",
            str(repair_path),
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ]
    )

    assert exit_code == 0
    assert json.loads(json_output.read_text(encoding="utf-8"))["passed"] is False


def test_main_enforce_mode_returns_one_when_gate_fails(tmp_path):
    nl2sql_path, repair_path = write_reports(tmp_path, below_threshold=True)

    exit_code = main(
        [
            "--nl2sql-report",
            str(nl2sql_path),
            "--repair-report",
            str(repair_path),
            "--json-output",
            str(tmp_path / "quality-gate.json"),
            "--markdown-output",
            str(tmp_path / "quality-gate.md"),
            "--enforce",
        ]
    )

    assert exit_code == 1


@pytest.mark.parametrize("invalid_content", [None, "{not-json"])
def test_main_returns_two_for_missing_or_invalid_report(tmp_path, invalid_content):
    nl2sql_path, repair_path = write_reports(tmp_path)
    if invalid_content is None:
        nl2sql_path.unlink()
    else:
        nl2sql_path.write_text(invalid_content, encoding="utf-8")

    exit_code = main(
        [
            "--nl2sql-report",
            str(nl2sql_path),
            "--repair-report",
            str(repair_path),
            "--json-output",
            str(tmp_path / "quality-gate.json"),
            "--markdown-output",
            str(tmp_path / "quality-gate.md"),
        ]
    )

    assert exit_code == 2
