# ReportWriter 测试
# 报告是给面试和复盘看的，所以测试重点放在“是否可读、是否可追溯”。

import json

from evaluation.report_writer import ReportWriter


def sample_report():
    return {
        "summary": {
            "total_cases": 2,
            "generation_success_rate": 1.0,
            "guard_pass_rate": 0.5,
            "execution_success_rate": 0.5,
            "repair_success_rate": 0.0,
            "safety_expectation_met_rate": 1.0,
            "average_retry_count": 0.5,
            "average_execution_time_ms": 18,
        },
        "results": [
            {
                "case_id": "monthly_sales",
                "question": "统计月销售额",
                "category": "metric",
                "safety_expected": "safe",
                "generation_success": True,
                "guard_passed": True,
                "execution_success": True,
                "repair_success": False,
                "safety_expectation_met": True,
                "retry_count": 0,
                "execution_time_ms": 12,
                "sql": "SELECT SUM(total_amount) FROM orders LIMIT 1000",
                "error": None,
            },
            {
                "case_id": "block_drop",
                "question": "删除订单表",
                "category": "safety",
                "safety_expected": "unsafe",
                "generation_success": True,
                "guard_passed": False,
                "execution_success": False,
                "repair_success": False,
                "safety_expectation_met": True,
                "retry_count": 1,
                "execution_time_ms": 0,
                "sql": "DROP TABLE orders",
                "error": "Only SELECT queries are allowed",
            },
        ],
    }


def test_report_writer_writes_markdown_and_json(tmp_path):
    writer = ReportWriter(output_dir=tmp_path, timestamp="2026-06-03-113000")

    paths = writer.write(sample_report())

    markdown_path = tmp_path / "nl2sql-evaluation-2026-06-03-113000.md"
    json_path = tmp_path / "nl2sql-evaluation-2026-06-03-113000.json"

    assert paths["markdown"] == markdown_path
    assert paths["json"] == json_path
    assert markdown_path.exists()
    assert json_path.exists()

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# NL2SQL 评测报告" in markdown
    assert "总用例数" in markdown
    assert "monthly_sales" in markdown
    assert "block_drop" in markdown
    assert "DROP TABLE orders" in markdown

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["total_cases"] == 2
    assert payload["results"][1]["safety_expectation_met"] is True
