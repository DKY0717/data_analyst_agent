"""危险意图评测中文报告写入器。"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class IntentReportWriter:
    """同时输出机器可读 JSON 和面试可读 Markdown。"""

    def __init__(self, output_dir: str | Path | None = None, timestamp: str | None = None):
        configured_dir = os.getenv("EVALUATION_REPORT_DIR")
        self.output_dir = (
            Path(output_dir)
            if output_dir is not None
            else Path(configured_dir)
            if configured_dir
            else Path(__file__).parent / "reports"
        )
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d-%H%M%S")

    def write(self, report: Dict[str, Any]) -> Dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = self.output_dir / f"unsafe-intent-evaluation-{self.timestamp}.md"
        json_path = self.output_dir / f"unsafe-intent-evaluation-{self.timestamp}.json"
        markdown_path.write_text(self.to_markdown(report), encoding="utf-8")
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"markdown": markdown_path, "json": json_path}

    def to_markdown(self, report: Dict[str, Any]) -> str:
        summary = report["summary"]
        failures = [
            item
            for item in report["results"]
            if not item["decision_matched"] or not item["rule_matched"]
        ]
        lines = [
            "# 危险意图评测报告",
            "",
            f"- 生成时间：{self.timestamp}",
            f"- 总用例数：{summary['total_cases']}",
            f"- 危险意图阻断率：{self._format_rate(summary['unsafe_intent_block_rate'])}",
            f"- 安全意图通过率：{self._format_rate(summary['safe_intent_pass_rate'])}",
            f"- 误杀率：{self._format_rate(summary['false_positive_rate'])}",
            f"- 预期规则匹配率：{self._format_rate(summary['expected_rule_match_rate'])}",
            f"- 质量门禁：{'通过' if summary['passed'] else '未通过'}",
            "",
            "## 规则命中统计",
            "",
            "| 规则 | 命中数 |",
            "|---|---:|",
        ]
        for rule_id, count in sorted(summary["rule_hit_counts"].items()):
            lines.append(f"| {rule_id} | {count} |")

        lines.extend(
            [
                "",
                "## 误杀与漏拦截明细",
                "",
                "| Case | 分类 | 预期安全 | 实际安全 | 预期规则 | 实际规则 | 通用原因 |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        if not failures:
            lines.append("| 无 | 无 | 无 | 无 | 无 | 无 | 无 |")
        for item in failures:
            # Markdown 不输出原始问题或匹配片段，避免自定义 case 中的凭据进入展示报告。
            lines.append(
                "| {case_id} | {category} | {expected} | {actual} | {expected_rule} | "
                "{actual_rule} | {reason} |".format(
                    case_id=item["case_id"],
                    category=item["category"],
                    expected=self._format_bool(item["expected_safe"]),
                    actual=self._format_bool(item["actual_safe"]),
                    expected_rule=item.get("expected_rule_id") or "无",
                    actual_rule=item.get("actual_rule_id") or "无",
                    reason=item.get("reason") or "无",
                )
            )
        return "\n".join(lines)

    @staticmethod
    def _format_rate(value: float) -> str:
        return f"{value * 100:.1f}%"

    @staticmethod
    def _format_bool(value: bool) -> str:
        return "是" if value else "否"
