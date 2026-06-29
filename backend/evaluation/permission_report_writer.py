# 数据权限评测报告写入器
# 输出适合 CI 读取的 JSON 和适合面试展示的中文 Markdown。

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class PermissionReportWriter:
    """将权限评测结果写成稳定文件，避免手工复制终端输出。"""

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
        """同时输出 Markdown 与 JSON，方便人读和机器回归。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = self.output_dir / f"permission-evaluation-{self.timestamp}.md"
        json_path = self.output_dir / f"permission-evaluation-{self.timestamp}.json"
        markdown_path.write_text(self.to_markdown(report), encoding="utf-8")
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"markdown": markdown_path, "json": json_path}

    def to_markdown(self, report: dict[str, Any]) -> str:
        """生成可展示报告，只暴露规则 ID 和表名，不输出完整行级策略。"""
        summary = report["summary"]
        lines = [
            "# 数据权限评测报告",
            "",
            f"- 生成时间：{self.timestamp}",
            f"- 总用例数：{summary['total_cases']}",
            f"- 权限决策准确率：{self._format_rate(summary['allowed_decision_accuracy'])}",
            f"- 阻断规则准确率：{self._format_rate(summary['blocked_rule_accuracy'])}",
            f"- 行级过滤预期命中率：{self._format_rate(summary['row_filter_expectation_accuracy'])}",
            f"- SQL 改写预期命中率：{self._format_rate(summary['authorized_sql_change_accuracy'])}",
            f"- 质量门禁：{'通过' if summary['passed'] else '未通过'}",
            "",
            "## Case 明细",
            "",
            "| Case | 角色 | 决策 | 阻断规则 | Row Filter | SQL 改写 | 结果 |",
            "|---|---|---|---|---|---|---|",
        ]

        for item in report["results"]:
            row_filter_rules = ", ".join(
                f"{rule['table']}:{rule['rule_id']}"
                for rule in item.get("row_filters_applied", [])
            ) or "无"
            lines.append(
                "| {case_id} | {roles} | {decision} | {rule} | {filters} | {changed} | {passed} |".format(
                    case_id=item["case_id"],
                    roles=",".join(item["roles"]),
                    decision=self._format_bool(item["actual_allowed"]),
                    rule=item.get("actual_blocked_rule") or "无",
                    filters=row_filter_rules,
                    changed=self._format_bool(item["actual_authorized_sql_changed"]),
                    passed="通过" if item["passed"] else "未通过",
                )
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_rate(value: float) -> str:
        return f"{value * 100:.1f}%"

    @staticmethod
    def _format_bool(value: bool) -> str:
        return "是" if value else "否"
