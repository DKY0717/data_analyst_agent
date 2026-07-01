import json

from evaluation.security_audit_report_writer import SecurityAuditReportWriter


def sample_report():
    return {
        "summary": {
            "passed": True,
            "deterministic_security_passed": True,
            "real_evaluation_provided": False,
            "quality_gate_provided": False,
            "missing_real_reports": ["nl2sql", "repair", "correctness"],
            "risk_count": 0,
        },
        "sections": {
            "intent_guard": {
                "title": "Intent Guard",
                "status": "passed",
                "provided": True,
                "metrics": {"unsafe_block_rate": 1.0},
            },
            "data_permission": {
                "title": "Data Permission Guard",
                "status": "passed",
                "provided": True,
                "metrics": {"allowed_decision_accuracy": 1.0},
            },
            "quality_gate": {
                "title": "Quality Gate",
                "status": "missing",
                "provided": False,
                "metrics": {},
            },
        },
        "evidence": [
            {
                "id": "permission.row_filter",
                "title": "Analyst 订单查询自动注入行级过滤",
                "status": "passed",
                "source": "PermissionEvaluationRunner",
            }
        ],
        "risks": [
            {
                "id": "real_evaluation.missing",
                "severity": "info",
                "message": "未提供真实 Qwen 端到端评测报告。",
            }
        ],
    }


def test_security_audit_writer_writes_json_and_markdown(tmp_path):
    writer = SecurityAuditReportWriter(output_dir=tmp_path, timestamp="ci")

    paths = writer.write(sample_report())

    assert paths["json"] == tmp_path / "security-audit-ci.json"
    assert paths["markdown"] == tmp_path / "security-audit-ci.md"
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["summary"]["passed"] is True
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "# 安全审计报告" in markdown
    assert "安全证据矩阵" in markdown
    assert "关键演示证据" in markdown
    assert "Analyst 订单查询自动注入行级过滤" in markdown


def test_security_audit_markdown_surfaces_input_completeness(tmp_path):
    writer = SecurityAuditReportWriter(output_dir=tmp_path, timestamp="ci")

    markdown = writer.to_markdown(sample_report())

    assert "## 输入完整性" in markdown
    assert "| 真实评测报告 | 未提供 | 缺失：nl2sql, repair, correctness |" in markdown
    assert "| Quality Gate | 未提供 | 未提供 quality-gate.json |" in markdown


def test_security_audit_markdown_does_not_leak_policy_or_secret_values(tmp_path):
    report = sample_report()
    report["sections"]["data_permission"]["metrics"]["debug_policy_expression"] = (
        "regions.region_name IN ('East')"
    )
    report["sections"]["intent_guard"]["metrics"]["api_key"] = (
        "fake_secret_value_that_must_not_render"
    )
    writer = SecurityAuditReportWriter(output_dir=tmp_path, timestamp="safe")

    markdown = writer.to_markdown(report)

    assert "debug_policy_expression" not in markdown
    assert "regions.region_name IN" not in markdown
    assert "fake_secret_value" not in markdown
