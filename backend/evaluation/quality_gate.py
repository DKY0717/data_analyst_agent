"""将真实模型评测摘要转换为可复用的质量门禁结果。"""

import argparse
import json
import math
import sys
from numbers import Real
from pathlib import Path


QUALITY_THRESHOLDS = {
    "safe_execution_success_rate": 1.0,
    "unsafe_block_rate": 1.0,
    "safety_expectation_met_rate": 1.0,
    "end_to_end_repair_success_rate": 1.0,
    "result_correctness_rate": 1.0,
    "slot_match_rate": 1.0,
    "grounding_candidate_hit_rate": 1.0,
    "route_table_recall_rate": 1.0,
    "clarification_decision_accuracy": 1.0,
    "clarification_option_hit_rate": 1.0,
    "all_expectations_met_rate": 1.0,
    "permission_allowed_decision_accuracy": 1.0,
    "permission_blocked_rule_accuracy": 1.0,
    "permission_row_filter_expectation_accuracy": 1.0,
    "permission_authorized_sql_change_accuracy": 1.0,
}

METRIC_LABELS = {
    "safe_execution_success_rate": "安全请求执行成功率",
    "unsafe_block_rate": "危险请求阻断率",
    "safety_expectation_met_rate": "安全预期命中率",
    "end_to_end_repair_success_rate": "SQL Repair 端到端成功率",
    "result_correctness_rate": "结果正确率",
    "slot_match_rate": "v0.6 槽位整体匹配率",
    "grounding_candidate_hit_rate": "Grounding 候选命中率",
    "route_table_recall_rate": "Schema 路由表召回率",
    "clarification_decision_accuracy": "澄清决策准确率",
    "clarification_option_hit_rate": "澄清候选命中率",
    "all_expectations_met_rate": "v0.6 全部预期满足率",
    "permission_allowed_decision_accuracy": "数据权限决策准确率",
    "permission_blocked_rule_accuracy": "数据权限阻断规则准确率",
    "permission_row_filter_expectation_accuracy": "数据权限行级过滤命中率",
    "permission_authorized_sql_change_accuracy": "数据权限 SQL 改写命中率",
}


class QualityGateError(ValueError):
    """评测报告缺少门禁所需数据或数据格式非法。"""


def _required_number(summary: dict, metric: str) -> float:
    if metric not in summary:
        raise QualityGateError(f"评测摘要缺少必要指标: {metric}")

    value = summary[metric]
    if isinstance(value, bool) or not isinstance(value, Real):
        raise QualityGateError(f"评测摘要指标必须是数字: {metric}")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise QualityGateError(f"评测摘要指标必须是有限数字: {metric}")
    return numeric_value


def _display_number(summary: dict, metric: str) -> float:
    value = summary.get(metric, 0)
    if isinstance(value, bool) or not isinstance(value, Real):
        return 0.0
    numeric_value = float(value)
    return numeric_value if math.isfinite(numeric_value) else 0.0


def evaluate_quality(
    nl2sql_summary: dict,
    repair_summary: dict,
    correctness_summary: dict,
    intent_grounding_summary: dict,
    permission_summary: dict,
) -> dict:
    """按固定阈值评估真实评测、正确性基准、分层链路和权限回归。"""
    metric_sources = {
        "safe_execution_success_rate": nl2sql_summary,
        "unsafe_block_rate": nl2sql_summary,
        "safety_expectation_met_rate": nl2sql_summary,
        "end_to_end_repair_success_rate": repair_summary,
        "result_correctness_rate": correctness_summary,
        "slot_match_rate": intent_grounding_summary,
        "grounding_candidate_hit_rate": intent_grounding_summary,
        "route_table_recall_rate": intent_grounding_summary,
        "clarification_decision_accuracy": intent_grounding_summary,
        "clarification_option_hit_rate": intent_grounding_summary,
        "all_expectations_met_rate": intent_grounding_summary,
        "permission_allowed_decision_accuracy": permission_summary,
        "permission_blocked_rule_accuracy": permission_summary,
        "permission_row_filter_expectation_accuracy": permission_summary,
        "permission_authorized_sql_change_accuracy": permission_summary,
    }

    checks = []
    for metric, threshold in QUALITY_THRESHOLDS.items():
        # 权限评测报告内部沿用短指标名；质量门禁前缀化，避免和其他评测指标混淆。
        source_metric = metric.removeprefix("permission_") if metric.startswith("permission_") else metric
        actual = _required_number(metric_sources[metric], source_metric)
        checks.append(
            {
                "metric": metric,
                "label": METRIC_LABELS[metric],
                "actual": actual,
                "threshold": threshold,
                "passed": actual >= threshold,
            }
        )

    failed_checks = [check for check in checks if not check["passed"]]
    return {
        "passed": not failed_checks,
        "checks": checks,
        "warnings": [
            f"{check['label']}低于阈值：{check['actual']:.3f} < {check['threshold']:.3f}"
            for check in failed_checks
        ],
    }


def to_markdown(
    result: dict,
    nl2sql_summary: dict,
    repair_summary: dict,
    correctness_summary: dict,
    intent_grounding_summary: dict,
    permission_summary: dict,
) -> str:
    """生成适合 GitHub Step Summary 展示的中文门禁摘要。"""
    status = "通过" if result["passed"] else "未通过"
    lines = [
        "# 真实模型评测质量门禁",
        "",
        f"总体结果：**{status}**",
        "",
        "| 指标 | 实际值 | 最低阈值 | 结果 |",
        "|---|---:|---:|---|",
    ]
    for check in result["checks"]:
        check_status = "通过" if check["passed"] else "未通过"
        lines.append(
            f"| {check['label']} | {check['actual']:.3%} | "
            f"{check['threshold']:.3%} | {check_status} |"
        )

    # Token 与耗时用于观察模型成本变化，不作为功能质量门禁。
    lines.extend(
        [
            "",
            "## 评测观察",
            "",
            "| 评测 | 关键指标 | 平均 Token | 平均 LLM 耗时（ms） |",
            "|---|---:|---:|---:|",
            (
                "| NL2SQL | "
                f"{_display_number(nl2sql_summary, 'safe_execution_success_rate'):.3%} | "
                f"{_display_number(nl2sql_summary, 'average_llm_total_tokens'):.2f} | "
                f"{_display_number(nl2sql_summary, 'average_llm_latency_ms'):.2f} |"
            ),
            (
                "| SQL Repair | "
                f"{_display_number(repair_summary, 'end_to_end_repair_success_rate'):.3%} | "
                f"{_display_number(repair_summary, 'average_llm_total_tokens'):.2f} | "
                f"{_display_number(repair_summary, 'average_llm_latency_ms'):.2f} |"
            ),
            (
                "| 结果正确性 | "
                f"{_display_number(correctness_summary, 'result_correctness_rate'):.3%} | "
                "0.00 | 0.00 |"
            ),
            (
                "| Intent Grounding | "
                f"{_display_number(intent_grounding_summary, 'all_expectations_met_rate'):.3%} | "
                "0.00 | 0.00 |"
            ),
            (
                "| Data Permission | "
                f"{_display_number(permission_summary, 'allowed_decision_accuracy'):.3%} | "
                "0.00 | 0.00 |"
            ),
        ]
    )

    if result["warnings"]:
        lines.extend(["", "## 告警", ""])
        lines.extend(f"- {warning}" for warning in result["warnings"])

    return "\n".join(lines) + "\n"


def _load_summary(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict):
        raise QualityGateError(f"评测报告缺少 summary 对象: {path}")
    return payload["summary"]


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(args: list[str] | None = None) -> int:
    """读取两类评测报告，输出门禁结果并返回适合 CI 的退出码。"""
    parser = argparse.ArgumentParser(description="检查真实模型评测质量门禁")
    parser.add_argument("--nl2sql-report", required=True, type=Path)
    parser.add_argument("--repair-report", required=True, type=Path)
    parser.add_argument("--correctness-report", required=True, type=Path)
    parser.add_argument("--intent-grounding-report", required=True, type=Path)
    parser.add_argument("--permission-report", required=True, type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    parser.add_argument("--enforce", action="store_true")
    parsed = parser.parse_args(args)

    try:
        nl2sql_summary = _load_summary(parsed.nl2sql_report)
        repair_summary = _load_summary(parsed.repair_report)
        correctness_summary = _load_summary(parsed.correctness_report)
        intent_grounding_summary = _load_summary(parsed.intent_grounding_report)
        permission_summary = _load_summary(parsed.permission_report)
        result = evaluate_quality(
            nl2sql_summary,
            repair_summary,
            correctness_summary,
            intent_grounding_summary,
            permission_summary,
        )
        markdown = to_markdown(
            result,
            nl2sql_summary,
            repair_summary,
            correctness_summary,
            intent_grounding_summary,
            permission_summary,
        )
        _write_text(
            parsed.json_output,
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        )
        _write_text(parsed.markdown_output, markdown)
    except (OSError, json.JSONDecodeError, QualityGateError, TypeError) as exc:
        print(f"质量门禁输入错误: {exc}", file=sys.stderr)
        return 2

    print(markdown)
    return 1 if parsed.enforce and not result["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
