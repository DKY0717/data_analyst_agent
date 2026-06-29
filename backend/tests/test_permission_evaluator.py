from evaluation.permission_evaluator import (
    PermissionEvaluationCase,
    PermissionEvaluationRunner,
)


def test_permission_evaluator_default_cases_pass(monkeypatch):
    monkeypatch.delenv("DATA_PERMISSION_POLICY_PATH", raising=False)

    report = PermissionEvaluationRunner().evaluate_all()

    summary = report["summary"]
    assert summary["total_cases"] == 5
    assert summary["allowed_decision_accuracy"] == 1.0
    assert summary["blocked_rule_accuracy"] == 1.0
    assert summary["row_filter_expectation_accuracy"] == 1.0
    assert summary["authorized_sql_change_accuracy"] == 1.0
    assert summary["passed"] is True
    assert all(item["passed"] for item in report["results"])
    assert "SELECT customer_id FROM customers" not in repr(report)


def test_permission_evaluator_records_mismatch_without_policy_dump(monkeypatch):
    monkeypatch.delenv("DATA_PERMISSION_POLICY_PATH", raising=False)
    case = PermissionEvaluationCase(
        case_id="wrong_expectation",
        description="故意设置错误预期，验证评测报告能稳定呈现失败。",
        roles=["analyst"],
        sql="SELECT customer_name FROM customers LIMIT 1000",
        expected_allowed=True,
        expected_blocked_rule=None,
        expect_row_filter=False,
        expect_authorized_sql_changed=False,
    )

    report = PermissionEvaluationRunner(cases=[case]).evaluate_all()
    result = report["results"][0]

    assert report["summary"]["passed"] is False
    assert result["passed"] is False
    assert result["decision_matched"] is False
    assert result["actual_allowed"] is False
    assert result["actual_blocked_rule"] == "block_unauthorized_column"
    assert result["error_type"] is None
    assert "ROLE_POLICIES" not in repr(report)
