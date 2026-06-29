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


def test_build_security_audit_report_with_real_reports_and_quality_gate():
    nl2sql = {
        "summary": {
            "passed": True,
            "safe_execution_success_rate": 1.0,
            "unsafe_block_rate": 1.0,
            "safety_expectation_met_rate": 1.0,
        }
    }
    repair = {"summary": {"passed": True, "end_to_end_repair_success_rate": 1.0}}
    correctness = {"summary": {"passed": True, "result_correctness_rate": 1.0}}
    quality_gate = {
        "passed": True,
        "checks": [{"metric": "safe_execution_success_rate", "passed": True}],
    }

    report = build_security_audit_report(
        nl2sql_report=nl2sql,
        repair_report=repair,
        correctness_report=correctness,
        quality_gate_report=quality_gate,
    )

    assert report["summary"]["passed"] is True
    assert report["summary"]["real_evaluation_provided"] is True
    assert report["summary"]["quality_gate_provided"] is True
    assert report["summary"]["missing_real_reports"] == []
    assert report["sections"]["quality_gate"]["status"] == "passed"
    assert any(item["id"] == "quality_gate.thresholds" for item in report["evidence"])


def test_load_optional_report_rejects_missing_path(tmp_path):
    with pytest.raises(SecurityAuditInputError, match="does not exist"):
        load_optional_report(tmp_path / "missing.json", "nl2sql")


def test_main_writes_reports_and_prints_json(tmp_path, capsys):
    exit_code = main(
        [
            "--write-report",
            "--json",
            "--output-dir",
            str(tmp_path),
            "--timestamp",
            "ci",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "security-audit-ci.json").exists()
    assert (tmp_path / "security-audit-ci.md").exists()
    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["passed"] is True


def test_main_returns_one_when_strict_real_reports_are_missing(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path), "--fail-on-missing-real-reports"])

    assert exit_code == 1


def test_main_returns_two_for_invalid_json(tmp_path, capsys):
    bad_report = tmp_path / "bad.json"
    bad_report.write_text("{bad", encoding="utf-8")

    exit_code = main(["--nl2sql-report", str(bad_report)])

    assert exit_code == 2
    assert "not valid JSON" in capsys.readouterr().err
