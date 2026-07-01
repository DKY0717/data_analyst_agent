# 安全审计报告写入器
# 同一份审计结果输出 JSON 和 Markdown，服务自动化检查与面试展示。

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


SAFE_METRIC_LABELS = {
    "total_cases": "用例数",
    "unsafe_block_rate": "危险请求阻断率",
    "unsafe_intent_block_rate": "危险意图提前阻断率",
    "safety_expectation_met_rate": "安全预期命中率",
    "safe_execution_success_rate": "安全请求执行成功率",
    "end_to_end_repair_success_rate": "SQL Repair 端到端成功率",
    "result_correctness_rate": "结果正确率",
    "all_expectations_met_rate": "全部预期满足率",
    "allowed_decision_accuracy": "权限决策准确率",
    "blocked_rule_accuracy": "阻断规则准确率",
    "row_filter_expectation_accuracy": "行级过滤命中率",
    "authorized_sql_change_accuracy": "SQL 改写命中率",
}


class SecurityAuditReportWriter:
    """将安全审计报告写入固定目录，避免手工拼接评测证据。"""

    def __init__(self, output_dir: str | Path | None = None, timestamp: str | None = None):
        configured_dir = os.getenv("EVALUATION_REPORT_DIR")
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        elif configured_dir:
            self.output_dir = Path(configured_dir)
        else:
            self.output_dir = Path(__file__).parent / "reports"
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d-%H%M%S")

    def write(self, report: dict[str, Any]) -> dict[str, Path]:
        """同时输出 Markdown 与 JSON，返回路径供 CLI 和测试使用。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = self.output_dir / f"security-audit-{self.timestamp}.md"
        json_path = self.output_dir / f"security-audit-{self.timestamp}.json"
        markdown_path.write_text(self.to_markdown(report), encoding="utf-8")
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"markdown": markdown_path, "json": json_path}

    def to_markdown(self, report: dict[str, Any]) -> str:
        """生成面试可读报告，只渲染白名单指标，避免泄露策略和密钥。"""
        summary = report["summary"]
        status = "通过" if summary["passed"] else "未通过"
        lines = [
            "# 安全审计报告",
            "",
            f"- 生成时间：{self.timestamp}",
            f"- 总体结果：{status}",
            f"- 确定性安全检查：{'通过' if summary['deterministic_security_passed'] else '未通过'}",
            f"- 真实评测输入：{'已提供' if summary['real_evaluation_provided'] else '未提供'}",
            f"- Quality Gate：{'已提供' if summary['quality_gate_provided'] else '未提供'}",
            f"- 风险数：{summary['risk_count']}",
            "",
            "## 安全证据矩阵",
            "",
            "| 模块 | 状态 | 输入 | 关键指标 |",
            "|---|---|---|---|",
        ]
        for section in report["sections"].values():
            lines.append(
                "| {title} | {status} | {provided} | {metrics} |".format(
                    title=section["title"],
                    status=self._status_label(section["status"]),
                    provided="已提供" if section.get("provided") else "未提供",
                    metrics=self._format_metrics(section.get("metrics", {})),
                )
            )

        missing_real_reports = summary.get("missing_real_reports", [])
        real_report_note = (
            "已纳入 NL2SQL / Repair / Result Correctness 报告"
            if summary["real_evaluation_provided"]
            else f"缺失：{', '.join(missing_real_reports)}"
        )
        quality_gate_note = (
            "已纳入 quality-gate.json"
            if summary["quality_gate_provided"]
            else "未提供 quality-gate.json"
        )
        lines.extend(
            [
                "",
                "## 输入完整性",
                "",
                "| 输入 | 状态 | 说明 |",
                "|---|---|---|",
                (
                    "| 真实评测报告 | "
                    f"{'已提供' if summary['real_evaluation_provided'] else '未提供'} | "
                    f"{real_report_note} |"
                ),
                (
                    "| Quality Gate | "
                    f"{'已提供' if summary['quality_gate_provided'] else '未提供'} | "
                    f"{quality_gate_note} |"
                ),
            ]
        )

        lines.extend(["", "## 关键演示证据", "", "| 证据 | 来源 | 状态 |", "|---|---|---|"])
        for item in report["evidence"]:
            lines.append(
                f"| {item['title']} | {item['source']} | {self._status_label(item['status'])} |"
            )

        if report["risks"]:
            lines.extend(["", "## 缺失输入和风险说明", ""])
            for risk in report["risks"]:
                lines.append(f"- [{risk['severity']}] {risk['message']}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _status_label(status: str) -> str:
        return {"passed": "通过", "failed": "未通过", "missing": "未提供"}.get(status, status)

    def _format_metrics(self, metrics: dict[str, Any]) -> str:
        visible = []
        for key, label in SAFE_METRIC_LABELS.items():
            if key in metrics:
                visible.append(f"{label}: {self._format_value(metrics[key])}")
        return "<br>".join(visible) if visible else "无"

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, float):
            return f"{value:.1%}"
        return str(value)
