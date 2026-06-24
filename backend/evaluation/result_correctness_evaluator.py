"""使用黄金参考 SQL 评估 Agent 分析结果是否正确。"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List

import yaml

from app.agents.graph import get_agent_graph
from app.utils.logger import logger
from evaluation.correctness_report_writer import CorrectnessReportWriter
from evaluation.reference_query_runner import reference_query_runner
from evaluation.result_comparator import result_comparator


AgentRunner = Callable[[str], Awaitable[Dict[str, Any]]]
SUMMARY_RATE_FIELDS = (
    "result_correctness_rate",
    "column_match_rate",
    "value_match_rate",
    "order_match_rate",
    "business_metric_accuracy",
    "reference_guard_pass_rate",
    "reference_execution_success_rate",
    "fixed_assertion_pass_rate",
)


class ResultCorrectnessEvaluator:
    """独立运行结果正确性基准，不改变现有 NL2SQL 生产工作流。"""

    def __init__(
        self,
        agent_runner: AgentRunner | None = None,
        reference_runner=reference_query_runner,
        comparator=None,
        case_file: str | Path | None = None,
    ):
        self.agent_runner = agent_runner or get_agent_graph().run
        self.reference_runner = reference_runner
        self.comparator = comparator or result_comparator
        self.case_file = (
            Path(case_file)
            if case_file
            else Path(__file__).parent / "cases" / "golden_result_cases.yaml"
        )

    def load_cases(self) -> List[Dict[str, Any]]:
        """加载固定黄金 case，保证不同版本使用同一评价口径。"""
        with self.case_file.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file)
        cases = payload.get("cases") if isinstance(payload, dict) else None
        if not isinstance(cases, list):
            raise ValueError("黄金 case 文件必须包含 cases 列表")
        return cases

    async def evaluate_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """评估单条 case；只保留 SQL、指标和有限差异，不保存完整结果集。"""
        result = self._base_result(case)
        try:
            agent_state = await self.agent_runner(case["question"])
            if not isinstance(agent_state, dict):
                raise ValueError("Agent 返回结果必须是字典")

            result["agent_sql"] = (
                agent_state.get("validated_sql")
                or agent_state.get("generated_sql")
                or ""
            )
            agent_query_result = agent_state.get("query_result")
            result["agent_execution_success"] = (
                agent_state.get("execution_success") is True
                and isinstance(agent_query_result, dict)
            )
            if not result["agent_execution_success"]:
                result["failure_type"] = "agent_execution_failed"
                return result

            reference_result = self.reference_runner.run(case["reference_sql"])
            if not isinstance(reference_result, dict):
                raise ValueError("ReferenceQueryRunner 返回结果必须是字典")
            result["reference_guard_passed"] = (
                reference_result.get("guard_passed") is True
            )
            result["reference_execution_success"] = (
                reference_result.get("execution_success") is True
            )
            if not result["reference_guard_passed"]:
                result["failure_type"] = "reference_guard_blocked"
                return result
            if not result["reference_execution_success"]:
                result["failure_type"] = "reference_execution_failed"
                return result

            comparison = self.comparator.compare(
                actual=agent_query_result,
                expected=reference_result,
                comparison=case["comparison"],
                fixed_assertions=case.get("fixed_assertions"),
            )
            if not isinstance(comparison, dict):
                raise ValueError("ResultComparator 返回结果必须是字典")
            result.update(
                {
                    "columns_matched": comparison.get("columns_matched") is True,
                    "values_matched": comparison.get("values_matched") is True,
                    "order_matched": comparison.get("order_matched") is True,
                    "fixed_assertions_matched": (
                        comparison.get("fixed_assertions_matched") is True
                    ),
                    "result_correct": comparison.get("result_correct") is True,
                    "comparison_failure_types": self._stable_list(
                        comparison.get("failure_types")
                    ),
                    "diff_samples": self._stable_list(
                        comparison.get("diff_samples")
                    )[:5],
                }
            )
            if not result["result_correct"]:
                failure_types = result["comparison_failure_types"]
                result["failure_type"] = (
                    failure_types[0] if failure_types else "comparison_failed"
                )
            return result
        except Exception as exc:
            # 异常文本可能包含数据库细节或凭据，只记录异常类型并返回稳定失败。
            logger.error("结果正确性评测 case 异常，异常类型=%s", type(exc).__name__)
            result["failure_type"] = "unexpected_error"
            return result

    async def evaluate_all(self) -> Dict[str, Any]:
        """顺序运行全部 case，确保单条失败不会阻断整批基准。"""
        results = []
        for case in self.load_cases():
            results.append(await self.evaluate_case(case))
        return {"summary": self.summarize_results(results), "results": results}

    def summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算结果正确性指标；空集合稳定返回 0，避免报告出现 NaN。"""
        total = len(results)
        if total == 0:
            return {"total_cases": 0, **{field: 0 for field in SUMMARY_RATE_FIELDS}}

        business_results = [
            item for item in results if item.get("category") == "business_metric"
        ]
        return {
            "total_cases": total,
            "result_correctness_rate": self._rate(results, "result_correct"),
            "column_match_rate": self._rate(results, "columns_matched"),
            "value_match_rate": self._rate(results, "values_matched"),
            "order_match_rate": self._rate(results, "order_matched"),
            "business_metric_accuracy": self._rate(
                business_results, "result_correct"
            ),
            "reference_guard_pass_rate": self._rate(
                results, "reference_guard_passed"
            ),
            "reference_execution_success_rate": self._rate(
                results, "reference_execution_success"
            ),
            "fixed_assertion_pass_rate": self._rate(
                results, "fixed_assertions_matched"
            ),
        }

    @staticmethod
    def _base_result(case: Dict[str, Any]) -> Dict[str, Any]:
        """集中定义稳定结果契约，失败路径也能被报告写入器直接消费。"""
        return {
            "case_id": case.get("id", "unknown"),
            "question": case.get("question", ""),
            "category": case.get("category", "unknown"),
            "agent_sql": "",
            "agent_execution_success": False,
            "reference_guard_passed": False,
            "reference_execution_success": False,
            "columns_matched": False,
            "values_matched": False,
            "order_matched": False,
            "fixed_assertions_matched": False,
            "result_correct": False,
            "failure_type": None,
            "comparison_failure_types": [],
            "diff_samples": [],
        }

    @staticmethod
    def _stable_list(value: Any) -> list:
        return list(value) if isinstance(value, (list, tuple)) else []

    @staticmethod
    def _rate(results: List[Dict[str, Any]], key: str) -> float:
        if not results:
            return 0
        return sum(1 for item in results if item.get(key) is True) / len(results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行结果正确性黄金基准")
    parser.add_argument("--case-file", help="自定义黄金 case YAML 路径")
    return parser.parse_args()


async def main_async(case_file: str | Path | None = None) -> Dict[str, Any]:
    """运行完整基准并输出汇总和中文报告路径。"""
    report = await ResultCorrectnessEvaluator(case_file=case_file).evaluate_all()
    paths = CorrectnessReportWriter().write(report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Result correctness report: {paths['markdown']}")
    return report


def main() -> int:
    args = parse_args()
    try:
        asyncio.run(main_async(args.case_file))
        return 0
    except (OSError, ValueError, yaml.YAMLError) as exc:
        logger.error("结果正确性评测初始化失败，异常类型=%s", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
