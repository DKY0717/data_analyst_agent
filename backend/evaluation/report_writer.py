# NL2SQL 评测报告生成器
# 将同一份结构化评测结果输出为 Markdown 和 JSON，兼顾面试展示与后续自动化分析。

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class ReportWriter:
    """把评测结果写入固定目录，形成可追溯的版本化报告。"""

    def __init__(self, output_dir: str | Path | None = None, timestamp: str | None = None):
        self.output_dir = Path(output_dir) if output_dir else Path(__file__).parent / "reports"
        # 使用时间戳避免覆盖历史报告，方便比较不同版本的 Agent 表现。
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d-%H%M%S")

    def write(self, report: Dict[str, Any]) -> Dict[str, Path]:
        """同时写 Markdown 和 JSON；返回路径便于 CLI 或测试继续处理。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = self.output_dir / f"nl2sql-evaluation-{self.timestamp}.md"
        json_path = self.output_dir / f"nl2sql-evaluation-{self.timestamp}.json"

        markdown_path.write_text(self.to_markdown(report), encoding="utf-8")
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "markdown": markdown_path,
            "json": json_path,
        }

    def to_markdown(self, report: Dict[str, Any]) -> str:
        """生成面试可读报告，突出指标、失败点和安全拦截结果。"""
        summary = report["summary"]
        results = report["results"]

        lines = [
            "# NL2SQL 评测报告",
            "",
            f"- 生成时间：{self.timestamp}",
            f"- 总用例数：{summary['total_cases']}",
            f"- SQL 生成成功率：{self._format_rate(summary['generation_success_rate'])}",
            f"- SQL Guard 通过率：{self._format_rate(summary['guard_pass_rate'])}",
            f"- SQL 执行成功率：{self._format_rate(summary['execution_success_rate'])}",
            f"- SQL 修复成功率：{self._format_rate(summary['repair_success_rate'])}",
            f"- 安全预期命中率：{self._format_rate(summary['safety_expectation_met_rate'])}",
            f"- 平均重试次数：{summary['average_retry_count']:.2f}",
            f"- 平均执行耗时：{summary['average_execution_time_ms']:.2f} ms",
            "",
            "## Case 明细",
            "",
            "| Case | 分类 | 安全预期 | 生成 | Guard | 执行 | 修复 | 安全命中 | 重试 | 耗时(ms) |",
            "|---|---|---|---|---|---|---|---|---:|---:|",
        ]

        for item in results:
            lines.append(
                "| {case_id} | {category} | {safety_expected} | {generation} | {guard} | "
                "{execution} | {repair} | {safety} | {retry_count} | {execution_time_ms} |".format(
                    case_id=item["case_id"],
                    category=item["category"],
                    safety_expected=item["safety_expected"],
                    generation=self._format_bool(item["generation_success"]),
                    guard=self._format_bool(item["guard_passed"]),
                    execution=self._format_bool(item["execution_success"]),
                    repair=self._format_bool(item["repair_success"]),
                    safety=self._format_bool(item["safety_expectation_met"]),
                    retry_count=item["retry_count"],
                    execution_time_ms=item["execution_time_ms"],
                )
            )

        lines.extend(["", "## SQL 与错误摘录", ""])

        for item in results:
            # SQL 与错误单独展开，避免主表过宽；面试时也更容易指向具体 case 讲取舍。
            lines.extend(
                [
                    f"### {item['case_id']}",
                    "",
                    f"- 问题：{item['question']}",
                    f"- SQL：`{item['sql']}`",
                    f"- 错误：{item['error'] or '无'}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _format_rate(self, value: float) -> str:
        return f"{value * 100:.1f}%"

    def _format_bool(self, value: bool) -> str:
        return "是" if value else "否"
