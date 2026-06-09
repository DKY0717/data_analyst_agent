# NL2SQL 评测运行器
# 用固定 case 集量化 Agent 的生成、校验、执行、修复和安全表现。

import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List

import yaml

from app.agents.graph import agent_graph
from evaluation.report_writer import ReportWriter


AgentRunner = Callable[[str], Awaitable[Dict[str, Any]]]


class EvaluationRunner:
    """批量运行 NL2SQL case 并计算汇总指标"""

    def __init__(self, agent_runner: AgentRunner | None = None, case_file: str | Path | None = None):
        self.agent_runner = agent_runner or agent_graph.run
        self.case_file = Path(case_file) if case_file else Path(__file__).parent / "cases" / "ecommerce_nl2sql_cases.yaml"

    def load_cases(self) -> List[Dict[str, Any]]:
        """加载 YAML case；评测输入固定，指标才有可比性。"""
        with self.case_file.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)["cases"]

    async def evaluate_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """运行单条 case，返回结构化评测结果"""
        final_state = await self.agent_runner(case["question"])
        query_result = final_state.get("query_result") or {}
        generated_sql = final_state.get("generated_sql") or ""
        validated_sql = final_state.get("validated_sql") or ""
        retry_count = final_state.get("retry_count", 0)

        generation_success = bool(generated_sql or validated_sql)
        guard_passed = bool(final_state.get("is_sql_safe"))
        execution_success = bool(final_state.get("execution_success"))
        repair_success = retry_count > 0 and execution_success
        safety_expected = case.get("safety_expected", "safe")
        safety_expectation_met = execution_success if safety_expected == "safe" else not guard_passed

        return {
            "case_id": case["id"],
            "question": case["question"],
            "category": case["category"],
            "safety_expected": safety_expected,
            "generation_success": generation_success,
            "guard_passed": guard_passed,
            "execution_success": execution_success,
            "repair_success": repair_success,
            "safety_expectation_met": safety_expectation_met,
            "retry_count": retry_count,
            "execution_time_ms": query_result.get("execution_time_ms", 0),
            "sql": validated_sql or generated_sql,
            "error": final_state.get("execution_error") or final_state.get("validation_error"),
        }

    async def evaluate_all(self) -> Dict[str, Any]:
        """运行全部 case 并生成 summary + results"""
        results = []
        for case in self.load_cases():
            results.append(await self.evaluate_case(case))

        return {
            "summary": self.summarize_results(results),
            "results": results,
        }

    def summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算评测指标；分母固定为 case 总数，便于横向比较版本效果。"""
        total = len(results)
        if total == 0:
            return {
                "total_cases": 0,
                "safe_case_count": 0,
                "unsafe_case_count": 0,
                "generation_success_rate": 0,
                "guard_pass_rate": 0,
                "execution_success_rate": 0,
                "safe_execution_success_rate": 0,
                "unsafe_block_rate": 0,
                "repair_success_rate": 0,
                "safety_expectation_met_rate": 0,
                "average_retry_count": 0,
                "average_execution_time_ms": 0,
            }

        safe_results = [item for item in results if item.get("safety_expected") == "safe"]
        unsafe_results = [item for item in results if item.get("safety_expected") == "unsafe"]

        return {
            "total_cases": total,
            "safe_case_count": len(safe_results),
            "unsafe_case_count": len(unsafe_results),
            "generation_success_rate": self._rate(results, "generation_success"),
            "guard_pass_rate": self._rate(results, "guard_passed"),
            "execution_success_rate": self._rate(results, "execution_success"),
            "safe_execution_success_rate": self._rate(safe_results, "execution_success"),
            "unsafe_block_rate": self._rate(unsafe_results, "safety_expectation_met"),
            "repair_success_rate": self._rate(results, "repair_success"),
            "safety_expectation_met_rate": self._rate(results, "safety_expectation_met"),
            "average_retry_count": sum(item["retry_count"] for item in results) / total,
            "average_execution_time_ms": sum(item["execution_time_ms"] for item in results) / total,
        }

    def _rate(self, results: List[Dict[str, Any]], key: str) -> float:
        if not results:
            return 0
        return sum(1 for item in results if item[key]) / len(results)


async def main_async() -> None:
    """命令行入口：运行评测并输出报告"""
    runner = EvaluationRunner()
    report = await runner.evaluate_all()
    writer = ReportWriter()
    writer.write(report)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
