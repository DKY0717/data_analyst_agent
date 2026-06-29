import json
from pathlib import Path

import pytest

from evaluation.permission_evaluator import PermissionEvaluationCase
from evaluation.security_audit_exporter import (
    SecurityAuditInputError,
    build_security_audit_report,
    load_optional_report,
    main,
)


def test_build_security_audit_report_without_real_reports_marks_missing_inputs():
    report = build_security_audit_report()

    assert report["summary"]["passed"] is True
    assert report["summary"]["deterministic_security_passed"] is True
    assert report["summary"]["real_evaluation_provided"] is False
    assert report["summary"]["quality_gate_provided"] is False
    assert set(report["summary"]["missing_real_reports"]) == {
        "nl2sql",
        "repair",
        "correctness",
    }
    assert report["sections"]["intent_guard"]["provided"] is True
    assert report["sections"]["intent_grounding"]["provided"] is True
    assert report["sections"]["data_permission"]["provided"] is True
    assert report["sections"]["nl2sql_safety"]["status"] == "missing"
    assert any(item["id"] == "permission.row_filter" for item in report["evidence"])


def test_build_security_audit_report_marks_permission_failure():
    failing_case = PermissionEvaluationCase(
        case_id="forced_permission_failure",
        description="forced failure for audit summary",
        roles=["analyst"],
        sql="SELECT SUM(total_amount) FROM orders LIMIT 1000",
        expected_allowed=False,
        expected_blocked_rule="block_unauthorized_table",
        expect_row_filter=False,
        expect_authorized_sql_changed=False,
    )

    report = build_security_audit_report(permission_cases=[failing_case])

    assert report["summary"]["passed"] is False
    assert report["summary"]["deterministic_security_passed"] is False
    assert report["summary"]["risk_count"] >= 1
    assert report["sections"]["data_permission"]["status"] == "failed"


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
