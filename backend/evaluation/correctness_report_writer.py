"""将结果正确性黄金基准输出为中文 Markdown 和 JSON。"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


RESULT_FIELDS = (
    "case_id",
    "question",
    "category",
    "agent_sql",
    "agent_execution_success",
    "reference_guard_passed",
    "reference_execution_success",
    "columns_matched",
    "values_matched",
    "order_matched",
    "fixed_assertions_matched",
    "result_correct",
    "failure_type",
    "comparison_failure_types",
    "diff_samples",
)


class CorrectnessReportWriter:
    """输出机器可读 JSON 与面试可读 Markdown，同时限制失败结果明细。"""

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
        """写报告前过滤非契约字段，避免上游意外附带完整结果集。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_report = self._safe_report(report)
        markdown_path = (
            self.output_dir
            / f"result-correctness-evaluation-{self.timestamp}.md"
        )
        json_path = (
            self.output_dir
            / f"result-correctness-evaluation-{self.timestamp}.json"
        )
        markdown_path.write_text(self.to_markdown(safe_report), encoding="utf-8")
        json_path.write_text(
            json.dumps(safe_report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"markdown": markdown_path, "json": json_path}

    def to_markdown(self, report: Dict[str, Any]) -> str:
        """突出正确性指标，并最多展示五条有限差异样本。"""
        safe_report = self._safe_report(report)
        summary = safe_report["summary"]
        failures = [
            item for item in safe_report["results"] if not item.get("result_correct")
        ][:5]
        lines = [
            "# 结果正确性黄金基准报告",
            "",
            f"- 生成时间：{self.timestamp}",
            f"- 总用例数：{summary.get('total_cases', 0)}",
            f"- 结果正确率：{self._format_rate(summary.get('result_correctness_rate', 0))}",
            f"- 列结构匹配率：{self._format_rate(summary.get('column_match_rate', 0))}",
            f"- 结果值匹配率：{self._format_rate(summary.get('value_match_rate', 0))}",
            f"- 排序匹配率：{self._format_rate(summary.get('order_match_rate', 0))}",
            f"- 核心业务指标命中率：{self._format_rate(summary.get('business_metric_accuracy', 0))}",
            f"- 参考 SQL Guard 通过率：{self._format_rate(summary.get('reference_guard_pass_rate', 0))}",
            f"- 参考 SQL 执行成功率：{self._format_rate(summary.get('reference_execution_success_rate', 0))}",
            f"- 固定断言通过率：{self._format_rate(summary.get('fixed_assertion_pass_rate', 0))}",
            "",
            "## 失败 Case 明细",
            "",
        ]
        if not failures:
            lines.append("无失败 Case。")
            return "\n".join(lines)

        for item in failures:
            # 只展示比较器已限量的差异摘要，不展示 Agent 或参考查询完整 rows。
            lines.extend(
                [
                    f"### {self._markdown_text(item.get('case_id', 'unknown'))}",
                    "",
                    f"- 分类：{self._markdown_text(item.get('category', 'unknown'))}",
                    f"- 问题：{self._markdown_text(item.get('question', ''))}",
                    f"- 失败类型：{self._markdown_text(item.get('failure_type') or 'unknown')}",
                    f"- Agent SQL：`{self._markdown_text(item.get('agent_sql', ''))}`",
                    "- 有限差异样本："
                    + self._markdown_text(
                        json.dumps(
                            item.get("diff_samples", [])[:5],
                            ensure_ascii=False,
                        )
                    ),
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _safe_report(report: Dict[str, Any]) -> Dict[str, Any]:
        """只允许稳定报告契约通过，未知大字段会在写盘前被丢弃。"""
        summary = report.get("summary", {}) if isinstance(report, dict) else {}
        results = report.get("results", []) if isinstance(report, dict) else []
        safe_results = []
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    safe_results.append(
                        {field: item.get(field) for field in RESULT_FIELDS if field in item}
                    )
        return {
            "summary": dict(summary) if isinstance(summary, dict) else {},
            "results": safe_results,
        }

    @staticmethod
    def _format_rate(value: Any) -> str:
        return f"{float(value) * 100:.1f}%"

    @staticmethod
    def _markdown_text(value: Any) -> str:
        return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
