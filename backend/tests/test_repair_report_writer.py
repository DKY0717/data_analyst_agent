# SQL Repair 评测报告测试
# 验证独立 Repair 报告可读、可追溯，并同时输出中文 Markdown 与 JSON。

import json

from evaluation.repair_report_writer import RepairReportWriter


def sample_report():
    return {
        "summary": {
            "total_cases": 1,
            "failure_injection_rate": 1.0,
            "repair_output_success_rate": 1.0,
            "repaired_guard_pass_rate": 1.0,
            "repair_execution_success_rate": 1.0,
            "intent_preservation_rate": 1.0,
            "end_to_end_repair_success_rate": 1.0,
            "average_execution_time_ms": 4,
            "average_llm_call_count": 1,
            "average_llm_total_tokens": 600,
            "average_llm_latency_ms": 900,
            "total_llm_estimated_cost": None,
            "cost_available": False,
        },
        "results": [
            {
                "case_id": "wrong_column",
                "description": "修复错误字段",
                "original_sql": "SELECT SUM(revenue) FROM orders",
                "original_guard_passed": True,
                "failure_injected": True,
                "original_error": "column revenue not found",
                "repair_output_success": True,
                "repaired_sql": "SELECT SUM(total_amount) FROM orders LIMIT 1000",
                "repair_reason": "改用 total_amount",
                "repaired_guard_passed": True,
                "execution_success": True,
                "intent_preserved": True,
                "end_to_end_success": True,
                "execution_time_ms": 4,
                "error": None,
                "llm_call_count": 1,
                "llm_total_tokens": 600,
                "llm_latency_ms": 900,
                "llm_estimated_cost": None,
            }
        ],
    }


def test_repair_report_writer_writes_markdown_and_json(tmp_path):
    writer = RepairReportWriter(output_dir=tmp_path, timestamp="2026-06-09-210000")

    paths = writer.write(sample_report())

    markdown_path = tmp_path / "sql-repair-evaluation-2026-06-09-210000.md"
    json_path = tmp_path / "sql-repair-evaluation-2026-06-09-210000.json"
    assert paths == {"markdown": markdown_path, "json": json_path}

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# SQL Repair 故障注入评测报告" in markdown
    assert "端到端修复成功率：100.0%" in markdown
    assert "wrong_column" in markdown
    assert "column revenue not found" in markdown
    assert "SELECT SUM(total_amount)" in markdown
    assert "平均 LLM Token：600.00" in markdown
    assert "LLM 估算总成本：未配置价格" in markdown

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["end_to_end_repair_success_rate"] == 1.0
    assert payload["results"][0]["intent_preserved"] is True
