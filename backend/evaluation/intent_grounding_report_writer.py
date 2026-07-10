"""v0.6 分层意图与 Grounding 评测报告写入器。"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class IntentGroundingReportWriter:
    """输出 JSON 给质量门禁，输出 Markdown 给面试展示。"""

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
        markdown_path = self.output_dir / f"intent-grounding-evaluation-{self.timestamp}.md"
        json_path = self.output_dir / f"intent-grounding-evaluation-{self.timestamp}.json"
        markdown_path.write_text(self.to_markdown(report), encoding="utf-8")
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"markdown": markdown_path, "json": json_path}

    def to_markdown(self, report: Dict[str, Any]) -> str:
        summary = report["summary"]
        failures = [item for item in report["results"] if not item["passed"]]
        lines = [
            "# v0.6 分层意图与 Schema Grounding 评测报告",
            "",
            f"- 生成时间：{self.timestamp}",
            f"- 总用例数：{summary['total_cases']}",
            f"- 槽位整体匹配率：{self._format_rate(summary['slot_match_rate'])}",
            f"- Grounding 候选命中率：{self._format_rate(summary['grounding_candidate_hit_rate'])}",
            f"- 路由表召回率：{self._format_rate(summary['route_table_recall_rate'])}",
            f"- 路由表精确率：{self._format_rate(summary['route_table_precision'])}",
            f"- JOIN 边准确率：{self._format_rate(summary['join_edge_accuracy'])}",
            f"- 澄清决策准确率：{self._format_rate(summary['clarification_decision_accuracy'])}",
            f"- 澄清候选命中率：{self._format_rate(summary['clarification_option_hit_rate'])}",
            f"- 全部预期满足率：{self._format_rate(summary['all_expectations_met_rate'])}",
            f"- 质量门禁：{'通过' if summary['passed'] else '未通过'}",
            "",
            "## Case 明细",
            "",
            "| Case | 分类 | 槽位 | 候选 | 路由表 | JOIN 边 | 澄清决策 | 澄清候选 | 结果 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]

        for item in report["results"]:
            slot_ok = (
                item["metrics_matched"]
                and item["dimensions_matched"]
                and item["filters_matched"]
                and item["ranking_matched"]
            )
            lines.append(
                "| {case_id} | {category} | {slot} | {candidate} | {route} | "
                "{joins} | {clarification} | {options} | {passed} |".format(
                    case_id=item["case_id"],
                    category=item["category"],
                    slot=self._format_bool(slot_ok),
                    candidate=self._format_bool(item["grounding_candidates_matched"]),
                    route=self._format_bool(item["route_tables_matched"]),
                    joins=self._format_bool(item["route_join_edges_matched"]),
                    clarification=self._format_bool(item["clarification_decision_matched"]),
                    options=self._format_bool(item["clarification_options_matched"]),
                    passed=self._format_bool(item["passed"]),
                )
            )

        lines.extend(["", "## 失败明细", ""])
        if not failures:
            lines.append("- 无")
        for item in failures[:5]:
            lines.extend(
                [
                    f"### {item['case_id']}",
                    "",
                    f"- 问题：{item['question']}",
                    f"- 实际指标：{', '.join(item['actual_metrics']) or '无'}",
                    f"- 实际维度：{', '.join(item['actual_dimensions']) or '无'}",
                    f"- 实际候选：{', '.join(item['actual_candidate_ids']) or '无'}",
                    f"- 实际路由表：{', '.join(item['actual_route_tables']) or '无'}",
                    f"- 实际 JOIN 边：{'; '.join(' = '.join(edge) for edge in item['actual_join_edges']) or '无'}",
                    f"- 是否澄清：{self._format_bool(item['clarification_required'])}",
                    "",
                ]
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_rate(value: float) -> str:
        return f"{value * 100:.1f}%"

    @staticmethod
    def _format_bool(value: bool) -> str:
        return "是" if value else "否"
