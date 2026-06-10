import pytest

from evaluation.quality_gate import QualityGateError, evaluate_quality, to_markdown


def passing_summaries():
    return (
        {
            "safe_execution_success_rate": 1.0,
            "unsafe_block_rate": 0.875,
            "safety_expectation_met_rate": 0.969,
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


def test_evaluate_quality_accepts_exact_31_of_32_safety_baseline():
    nl2sql_summary, repair_summary = passing_summaries()
    nl2sql_summary["safety_expectation_met_rate"] = 31 / 32

    result = evaluate_quality(nl2sql_summary, repair_summary)

    assert result["passed"] is True


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


def test_display_metrics_default_to_zero_without_affecting_gate():
    nl2sql_summary, repair_summary = passing_summaries()
    for summary in (nl2sql_summary, repair_summary):
        summary.pop("average_llm_total_tokens", None)
        summary.pop("average_llm_latency_ms", None)

    result = evaluate_quality(nl2sql_summary, repair_summary)
    markdown = to_markdown(result, nl2sql_summary, repair_summary)

    assert result["passed"] is True
    assert "0.00" in markdown
