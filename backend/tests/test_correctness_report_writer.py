"""结果正确性中文报告写入器测试。"""

import json

from evaluation.correctness_report_writer import CorrectnessReportWriter


def sample_report(failure_count=1):
    results = [
        {
            "case_id": f"case_{index}",
            "question": f"问题 {index}",
            "category": "business_metric",
            "agent_sql": "SELECT 1 AS value",
            "agent_execution_success": True,
            "reference_guard_passed": True,
            "reference_execution_success": True,
            "columns_matched": False,
            "values_matched": False,
            "order_matched": True,
            "fixed_assertions_matched": True,
            "result_correct": False,
            "failure_type": "column_mismatch",
            "comparison_failure_types": ["column_mismatch"],
            "diff_samples": [
                {
                    "actual_columns": ["actual"],
                    "expected_columns": ["expected"],
                }
            ],
        }
        for index in range(failure_count)
    ]
    return {
        "summary": {
            "total_cases": failure_count,
            "result_correctness_rate": 0,
            "column_match_rate": 0,
            "value_match_rate": 0,
            "order_match_rate": 1,
            "business_metric_accuracy": 0,
            "reference_guard_pass_rate": 1,
            "reference_execution_success_rate": 1,
            "fixed_assertion_pass_rate": 1,
        },
        "results": results,
    }


def test_writer_outputs_markdown_and_json(tmp_path):
    writer = CorrectnessReportWriter(
        output_dir=tmp_path, timestamp="2026-06-11-180000"
    )

    paths = writer.write(sample_report())

    assert paths["markdown"].name == (
        "result-correctness-evaluation-2026-06-11-180000.md"
    )
    assert paths["json"].name == "result-correctness-evaluation-2026-06-11-180000.json"
    markdown = paths["markdown"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert "# 结果正确性黄金基准报告" in markdown
    assert "结果正确率" in markdown
    assert "列结构匹配率" in markdown
    assert "结果值匹配率" in markdown
    assert "排序匹配率" in markdown
    assert "核心业务指标命中率" in markdown
    assert "参考 SQL Guard 通过率" in markdown
    assert "固定断言通过率" in markdown
    assert "失败 Case 明细" in markdown
    assert payload == sample_report()


def test_markdown_limits_failure_details_and_omits_full_result_fields(tmp_path):
    report = sample_report(failure_count=10)
    # 即使上游意外携带大结果字段，展示报告也不能输出这些内容。
    report["results"][0]["query_result"] = {"rows": [["sensitive-large-result"]]}
    writer = CorrectnessReportWriter(output_dir=tmp_path, timestamp="bounded")

    markdown = writer.to_markdown(report)

    assert markdown.count("### case_") == 5
    assert "case_5" not in markdown
    assert "sensitive-large-result" not in markdown
    assert "query_result" not in markdown


def test_writer_uses_evaluation_report_dir_when_output_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALUATION_REPORT_DIR", str(tmp_path))

    paths = CorrectnessReportWriter(timestamp="env-output").write(sample_report())

    assert paths["markdown"].parent == tmp_path
    assert paths["json"].parent == tmp_path
