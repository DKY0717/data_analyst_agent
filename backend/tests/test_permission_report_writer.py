import json

from evaluation.permission_report_writer import PermissionReportWriter


def sample_report():
    return {
        "summary": {
            "total_cases": 2,
            "allowed_decision_accuracy": 1.0,
            "blocked_rule_accuracy": 1.0,
            "row_filter_expectation_accuracy": 1.0,
            "authorized_sql_change_accuracy": 1.0,
            "passed": True,
        },
        "results": [
            {
                "case_id": "analyst_order_row_filter",
                "description": "analyst 查询订单指标时必须注入区域行级过滤。",
                "roles": ["analyst"],
                "expected_allowed": True,
                "actual_allowed": True,
                "decision_matched": True,
                "expected_blocked_rule": None,
                "actual_blocked_rule": None,
                "rule_matched": True,
                "expect_row_filter": True,
                "actual_row_filter": True,
                "row_filter_matched": True,
                "expect_authorized_sql_changed": True,
                "actual_authorized_sql_changed": True,
                "authorized_sql_change_matched": True,
                "row_filters_applied": [
                    {"table": "orders", "rule_id": "row_filter_region_scope"}
                ],
                "error_type": None,
                "passed": True,
            },
            {
                "case_id": "analyst_customer_name_blocked",
                "description": "analyst 不能访问客户姓名字段。",
                "roles": ["analyst"],
                "expected_allowed": False,
                "actual_allowed": False,
                "decision_matched": True,
                "expected_blocked_rule": "block_unauthorized_column",
                "actual_blocked_rule": "block_unauthorized_column",
                "rule_matched": True,
                "expect_row_filter": False,
                "actual_row_filter": False,
                "row_filter_matched": True,
                "expect_authorized_sql_changed": False,
                "actual_authorized_sql_changed": False,
                "authorized_sql_change_matched": True,
                "row_filters_applied": [],
                "error_type": None,
                "passed": True,
            },
        ],
    }


def test_permission_report_writer_outputs_markdown_and_json(tmp_path):
    writer = PermissionReportWriter(output_dir=tmp_path, timestamp="2026-06-29-210000")

    paths = writer.write(sample_report())

    assert paths["markdown"].name == "permission-evaluation-2026-06-29-210000.md"
    assert paths["json"].name == "permission-evaluation-2026-06-29-210000.json"
    markdown = paths["markdown"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert "# 数据权限评测报告" in markdown
    assert "权限决策准确率：100.0%" in markdown
    assert "analyst_order_row_filter" in markdown
    assert "row_filter_region_scope" in markdown
    assert "SELECT customer_id FROM customers" not in markdown
    assert payload == sample_report()


def test_permission_report_writer_uses_environment_report_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALUATION_REPORT_DIR", str(tmp_path))

    paths = PermissionReportWriter(timestamp="env-output").write(sample_report())

    assert paths["markdown"].parent == tmp_path
    assert paths["json"].parent == tmp_path
