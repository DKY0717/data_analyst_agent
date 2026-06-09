# SQL Repair 故障注入评测报告生成器
# 输出独立中文 Markdown 与 JSON，避免 Repair 指标和 NL2SQL 生成指标混在一起。

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class RepairReportWriter:
    """写入可追溯的 SQL Repair 故障注入评测报告。"""

    def __init__(self, output_dir: str | Path | None = None, timestamp: str | None = None):
        self.output_dir = Path(output_dir) if output_dir else Path(__file__).parent / "reports"
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d-%H%M%S")

    def write(self, report: Dict[str, Any]) -> Dict[str, Path]:
        """同时输出 Markdown 与 JSON。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = self.output_dir / f"sql-repair-evaluation-{self.timestamp}.md"
        json_path = self.output_dir / f"sql-repair-evaluation-{self.timestamp}.json"

        markdown_path.write_text(self.to_markdown(report), encoding="utf-8")
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"markdown": markdown_path, "json": json_path}

    def to_markdown(self, report: Dict[str, Any]) -> str:
        """生成突出真实错误、修复结果与意图保持的中文报告。"""
        summary = report["summary"]
        results = report["results"]
        lines = [
            "# SQL Repair 故障注入评测报告",
            "",
            f"- 生成时间：{self.timestamp}",
            f"- 总用例数：{summary['total_cases']}",
            f"- 故障注入成功率：{self._format_rate(summary['failure_injection_rate'])}",
            f"- Repair 输出成功率：{self._format_rate(summary['repair_output_success_rate'])}",
            f"- 修复后 Guard 通过率：{self._format_rate(summary['repaired_guard_pass_rate'])}",
            f"- 修复后执行成功率：{self._format_rate(summary['repair_execution_success_rate'])}",
            f"- 意图保持率：{self._format_rate(summary['intent_preservation_rate'])}",
            f"- 端到端修复成功率：{self._format_rate(summary['end_to_end_repair_success_rate'])}",
            f"- 平均修复后执行耗时：{summary['average_execution_time_ms']:.2f} ms",
            "",
            "## Case 明细",
            "",
            "| Case | 故障注入 | Repair 输出 | Guard | 执行 | 意图保持 | 端到端成功 | 耗时(ms) |",
            "|---|---|---|---|---|---|---|---:|",
        ]

        for item in results:
            lines.append(
                "| {case_id} | {failure} | {repair} | {guard} | {execution} | "
                "{intent} | {end_to_end} | {execution_time_ms} |".format(
                    case_id=item["case_id"],
                    failure=self._format_bool(item["failure_injected"]),
                    repair=self._format_bool(item["repair_output_success"]),
                    guard=self._format_bool(item["repaired_guard_passed"]),
                    execution=self._format_bool(item["execution_success"]),
                    intent=self._format_bool(item["intent_preserved"]),
                    end_to_end=self._format_bool(item["end_to_end_success"]),
                    execution_time_ms=item["execution_time_ms"],
                )
            )

        lines.extend(["", "## 修复明细", ""])
        for item in results:
            lines.extend(
                [
                    f"### {item['case_id']}",
                    "",
                    f"- 说明：{item['description']}",
                    f"- 原始 SQL：`{item['original_sql']}`",
                    f"- 原始数据库错误：{item['original_error'] or '无'}",
                    f"- 修复 SQL：`{item['repaired_sql'] or '无'}`",
                    f"- 修复原因：{item['repair_reason'] or '无'}",
                    f"- 最终错误：{item['error'] or '无'}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _format_rate(self, value: float) -> str:
        return f"{value * 100:.1f}%"

    def _format_bool(self, value: bool) -> str:
        return "是" if value else "否"
