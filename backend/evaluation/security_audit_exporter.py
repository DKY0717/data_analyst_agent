# 安全审计导出器
# 聚合确定性安全评测和可选真实评测报告，生成统一审计证据。

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evaluation.intent_evaluator import IntentEvaluationRunner
from evaluation.intent_grounding_evaluator import IntentGroundingEvaluationRunner
from evaluation.permission_evaluator import PermissionEvaluationCase, PermissionEvaluationRunner
from evaluation.security_audit_report_writer import SecurityAuditReportWriter


class SecurityAuditInputError(ValueError):
    """审计导出输入文件缺失或结构非法。"""


def load_optional_report(path: Path | None, report_name: str) -> dict[str, Any] | None:
    """读取带 summary 的可选评测报告；未提供路径时返回 None。"""
    if path is None:
        return None
    if not path.exists():
        raise SecurityAuditInputError(f"{report_name} report does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SecurityAuditInputError(f"{report_name} report is not valid JSON: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict):
        raise SecurityAuditInputError(f"{report_name} report must contain a summary object: {path}")
    return payload


def load_quality_gate_report(path: Path | None) -> dict[str, Any] | None:
    """读取 quality gate 结果；该文件顶层就是 passed/checks/warnings。"""
    if path is None:
        return None
    if not path.exists():
        raise SecurityAuditInputError(f"quality_gate report does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SecurityAuditInputError(
            f"quality_gate report is not valid JSON: {path}"
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("checks"), list):
        raise SecurityAuditInputError(f"quality_gate report must contain checks array: {path}")
    if not isinstance(payload.get("passed"), bool):
        raise SecurityAuditInputError(f"quality_gate report must contain boolean passed: {path}")
    return payload


def build_security_audit_report(
    *,
    nl2sql_report: dict[str, Any] | None = None,
    repair_report: dict[str, Any] | None = None,
    correctness_report: dict[str, Any] | None = None,
    quality_gate_report: dict[str, Any] | None = None,
    permission_cases: list[PermissionEvaluationCase] | None = None,
) -> dict[str, Any]:
    """构建统一安全审计报告；默认只运行确定性评测。"""
    intent_report = IntentEvaluationRunner().evaluate_all()
    grounding_report = IntentGroundingEvaluationRunner().evaluate_all()
    permission_report = PermissionEvaluationRunner(cases=permission_cases).evaluate_all()

    sections = {
        "intent_guard": _section(
            "Intent Guard",
            intent_report["summary"],
            intent_report["summary"].get("passed", False),
            provided=True,
        ),
        "nl2sql_safety": _optional_section(
            "NL2SQL Safety",
            nl2sql_report,
            ("safe_execution_success_rate", "unsafe_block_rate", "safety_expectation_met_rate"),
        ),
        "sql_repair": _optional_section(
            "SQL Repair",
            repair_report,
            ("end_to_end_repair_success_rate",),
        ),
        "result_correctness": _optional_section(
            "Result Correctness",
            correctness_report,
            ("result_correctness_rate",),
        ),
        "intent_grounding": _section(
            "Intent Grounding",
            grounding_report["summary"],
            grounding_report["summary"].get("passed", False),
            provided=True,
        ),
        "data_permission": _section(
            "Data Permission Guard",
            permission_report["summary"],
            permission_report["summary"].get("passed", False),
            provided=True,
        ),
        "quality_gate": _quality_gate_section(quality_gate_report),
    }

    risks = _collect_risks(sections, nl2sql_report, repair_report, correctness_report)
    deterministic_security_passed = (
        sections["intent_guard"]["status"] == "passed"
        and sections["intent_grounding"]["status"] == "passed"
        and sections["data_permission"]["status"] == "passed"
    )
    quality_gate_failed = sections["quality_gate"]["status"] == "failed"
    real_evaluation_provided = all(
        report is not None for report in (nl2sql_report, repair_report, correctness_report)
    )
    missing_real_reports = [
        name
        for name, report in {
            "nl2sql": nl2sql_report,
            "repair": repair_report,
            "correctness": correctness_report,
        }.items()
        if report is None
    ]

    return {
        "summary": {
            "passed": deterministic_security_passed and not quality_gate_failed,
            "deterministic_security_passed": deterministic_security_passed,
            "real_evaluation_provided": real_evaluation_provided,
            "quality_gate_provided": quality_gate_report is not None,
            "missing_real_reports": missing_real_reports,
            "risk_count": len(risks),
        },
        "sections": sections,
        "evidence": _build_evidence(intent_report, permission_report, quality_gate_report),
        "risks": risks,
    }


def _section(title: str, summary: dict[str, Any], passed: bool, *, provided: bool) -> dict[str, Any]:
    return {
        "title": title,
        "status": "passed" if passed else "failed",
        "provided": provided,
        "metrics": summary,
    }


def _optional_section(
    title: str,
    report: dict[str, Any] | None,
    metric_names: tuple[str, ...],
) -> dict[str, Any]:
    if report is None:
        return {"title": title, "status": "missing", "provided": False, "metrics": {}}
    summary = report["summary"]
    metrics = {name: summary[name] for name in metric_names if name in summary}
    passed = bool(summary.get("passed", True))
    return {
        "title": title,
        "status": "passed" if passed else "failed",
        "provided": True,
        "metrics": metrics,
    }


def _quality_gate_section(report: dict[str, Any] | None) -> dict[str, Any]:
    if report is None:
        return {"title": "Quality Gate", "status": "missing", "provided": False, "metrics": {}}
    return {
        "title": "Quality Gate",
        "status": "passed" if report.get("passed") else "failed",
        "provided": True,
        "metrics": {
            "total_cases": len(report.get("checks", [])),
            "all_expectations_met_rate": 1.0 if report.get("passed") else 0.0,
        },
    }


def _collect_risks(
    sections: dict[str, dict[str, Any]],
    nl2sql_report: dict[str, Any] | None,
    repair_report: dict[str, Any] | None,
    correctness_report: dict[str, Any] | None,
) -> list[dict[str, str]]:
    risks = []
    for key, section in sections.items():
        if section["status"] == "failed":
            risks.append(
                {
                    "id": f"{key}.failed",
                    "severity": "high",
                    "message": f"{section['title']} 未通过安全审计。",
                }
            )
    missing = [
        name
        for name, report in {
            "nl2sql": nl2sql_report,
            "repair": repair_report,
            "correctness": correctness_report,
        }.items()
        if report is None
    ]
    if missing:
        risks.append(
            {
                "id": "real_evaluation.missing",
                "severity": "info",
                "message": f"未提供真实模型端到端评测报告：{', '.join(missing)}。",
            }
        )
    return risks


def _build_evidence(
    intent_report: dict[str, Any],
    permission_report: dict[str, Any],
    quality_gate_report: dict[str, Any] | None,
) -> list[dict[str, str]]:
    evidence = [
        {
            "id": "intent.pre_llm_block",
            "title": "危险意图在 LLM 调用前被阻断",
            "status": "passed" if intent_report["summary"].get("passed") else "failed",
            "source": "IntentEvaluationRunner",
        },
        {
            "id": "permission.unauthorized_column",
            "title": "权限越权字段被 Data Permission Guard 阻断",
            "status": _case_status(permission_report, "analyst_customer_name_blocked"),
            "source": "PermissionEvaluationRunner",
        },
        {
            "id": "permission.row_filter",
            "title": "Analyst 订单查询自动注入行级过滤",
            "status": _case_status(permission_report, "analyst_order_row_filter"),
            "source": "PermissionEvaluationRunner",
        },
    ]
    if quality_gate_report is not None:
        evidence.append(
            {
                "id": "quality_gate.thresholds",
                "title": "Quality Gate 对核心指标执行 100% 阈值",
                "status": "passed" if quality_gate_report.get("passed") else "failed",
                "source": "evaluation.quality_gate",
            }
        )
    return evidence


def _case_status(report: dict[str, Any], case_id: str) -> str:
    for item in report["results"]:
        if item["case_id"] == case_id:
            return "passed" if item["passed"] else "failed"
    return "missing"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a consolidated security audit report")
    parser.add_argument("--json", action="store_true", help="print full JSON report")
    parser.add_argument("--write-report", action="store_true", help="write JSON and Markdown reports")
    parser.add_argument("--output-dir", help="directory for written reports")
    parser.add_argument("--timestamp", help="timestamp suffix for written reports")
    parser.add_argument("--nl2sql-report", type=Path)
    parser.add_argument("--repair-report", type=Path)
    parser.add_argument("--correctness-report", type=Path)
    parser.add_argument("--quality-gate-report", type=Path)
    parser.add_argument("--fail-on-missing-real-reports", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = build_security_audit_report(
            nl2sql_report=load_optional_report(args.nl2sql_report, "nl2sql"),
            repair_report=load_optional_report(args.repair_report, "repair"),
            correctness_report=load_optional_report(args.correctness_report, "correctness"),
            quality_gate_report=load_quality_gate_report(args.quality_gate_report),
        )
        if args.write_report:
            # CLI 输出复用 writer 的目录解析规则，便于本地和 CI 用同一套参数。
            SecurityAuditReportWriter(
                output_dir=args.output_dir,
                timestamp=args.timestamp,
            ).write(report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, SecurityAuditInputError, TypeError) as exc:
        print(f"安全审计导出输入错误: {exc}", file=sys.stderr)
        return 2

    if args.fail_on_missing_real_reports and report["summary"]["missing_real_reports"]:
        return 1
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
