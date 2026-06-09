# SQL Repair 故障注入评测器
# 用固定安全错误 SQL 获取真实数据库错误，再独立量化 Repair 的安全性、可执行性和意图保持能力。

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, List

import yaml

from app.agents.sql_repair import sql_repair_agent
from app.db.query_runner import query_runner
from app.db.schema_loader import schema_loader
from app.security.sql_guard import sql_guard
from evaluation.repair_report_writer import RepairReportWriter


class RepairEvaluationRunner:
    """运行确定性 SQL Repair 故障注入 case。"""

    def __init__(
        self,
        repair_agent=sql_repair_agent,
        guard=sql_guard,
        query_runner=query_runner,
        schema_loader: Callable[[], Dict[str, Any]] = schema_loader.get_full_schema,
        case_file: str | Path | None = None,
    ):
        self.repair_agent = repair_agent
        self.guard = guard
        self.query_runner = query_runner
        self.schema_loader = schema_loader
        self.case_file = (
            Path(case_file)
            if case_file
            else Path(__file__).parent / "cases" / "sql_repair_cases.yaml"
        )

    def load_cases(self) -> List[Dict[str, Any]]:
        """加载固定 Repair case，使真实基线可以重复运行。"""
        with self.case_file.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)["cases"]

    async def evaluate_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """运行单条故障注入、Repair、Guard、执行和意图检查流程。"""
        result = self._empty_result(case)

        original_guard = self.guard.validate(case["original_sql"])
        result["original_guard_passed"] = bool(original_guard["is_safe"])
        if not original_guard["is_safe"]:
            result["error"] = original_guard.get("reason")
            return result

        original_execution = self.query_runner.execute(original_guard["sanitized_sql"])
        if original_execution.get("success"):
            result["error"] = "错误 SQL 意外执行成功，未形成确定性故障注入"
            return result

        result["failure_injected"] = True
        result["original_error"] = original_execution.get("error")

        try:
            repair_output = await self.repair_agent.repair(
                case["original_sql"],
                result["original_error"] or "",
                self.schema_loader(),
            )
        except Exception as exc:
            # 单条 LLM 或 Repair 异常只记录结果，整批评测继续运行。
            result["error"] = str(exc)
            return result

        result["repair_output_success"] = True
        result["repaired_sql"] = repair_output.repaired_sql
        result["repair_reason"] = repair_output.repair_reason

        repaired_guard = self.guard.validate(repair_output.repaired_sql)
        result["repaired_guard_passed"] = bool(repaired_guard["is_safe"])
        if not repaired_guard["is_safe"]:
            result["error"] = repaired_guard.get("reason")
            return result

        repaired_execution = self.query_runner.execute(repaired_guard["sanitized_sql"])
        result["execution_success"] = bool(repaired_execution.get("success"))
        result["execution_time_ms"] = repaired_execution.get("execution_time_ms", 0)
        if not repaired_execution.get("success"):
            result["error"] = repaired_execution.get("error")

        result.update(self.check_intent(repaired_guard["sanitized_sql"], case))
        result["end_to_end_success"] = all(
            [
                result["failure_injected"],
                result["repair_output_success"],
                result["repaired_guard_passed"],
                result["execution_success"],
                result["intent_preserved"],
            ]
        )
        return result

    async def evaluate_all(self) -> Dict[str, Any]:
        """逐条运行 case；任一 case 的结构化失败不会终止整批。"""
        results = []
        for case in self.load_cases():
            try:
                results.append(await self.evaluate_case(case))
            except Exception as exc:
                # 依赖层意外异常也转换为稳定结果，保证真实长批次不会丢失后续 case。
                failed_result = self._empty_result(case)
                failed_result["error"] = str(exc)
                results.append(failed_result)
        return {"summary": self.summarize_results(results), "results": results}

    def check_intent(self, repaired_sql: str, case: Dict[str, Any]) -> Dict[str, bool]:
        """使用固定 SQL 片段规则检查修复是否保持原查询意图。"""
        normalized_sql = repaired_sql.lower()
        expected_tables_met = all(
            table.lower() in normalized_sql for table in case.get("expected_tables", [])
        )
        required_fragments_met = all(
            fragment.lower() in normalized_sql
            for fragment in case.get("required_sql_fragments", [])
        )
        forbidden_fragments_absent = all(
            fragment.lower() not in normalized_sql
            for fragment in case.get("forbidden_sql_fragments", [])
        )

        return {
            "expected_tables_met": expected_tables_met,
            "required_fragments_met": required_fragments_met,
            "forbidden_fragments_absent": forbidden_fragments_absent,
            "intent_preserved": all(
                [expected_tables_met, required_fragments_met, forbidden_fragments_absent]
            ),
        }

    def summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算独立 Repair 指标，分母固定为 Repair case 总数。"""
        total = len(results)
        if not total:
            return {
                "total_cases": 0,
                "failure_injection_rate": 0,
                "repair_output_success_rate": 0,
                "repaired_guard_pass_rate": 0,
                "repair_execution_success_rate": 0,
                "intent_preservation_rate": 0,
                "end_to_end_repair_success_rate": 0,
                "average_execution_time_ms": 0,
            }

        return {
            "total_cases": total,
            "failure_injection_rate": self._rate(results, "failure_injected"),
            "repair_output_success_rate": self._rate(results, "repair_output_success"),
            "repaired_guard_pass_rate": self._rate(results, "repaired_guard_passed"),
            "repair_execution_success_rate": self._rate(results, "execution_success"),
            "intent_preservation_rate": self._rate(results, "intent_preserved"),
            "end_to_end_repair_success_rate": self._rate(results, "end_to_end_success"),
            "average_execution_time_ms": sum(
                result["execution_time_ms"] for result in results
            ) / total,
        }

    def _rate(self, results: List[Dict[str, Any]], key: str) -> float:
        return sum(1 for result in results if result[key]) / len(results)

    def _empty_result(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """创建稳定结果结构，便于失败分支和报告统一消费。"""
        return {
            "case_id": case["id"],
            "description": case["description"],
            "original_sql": case["original_sql"],
            "original_guard_passed": False,
            "failure_injected": False,
            "original_error": None,
            "repair_output_success": False,
            "repaired_sql": "",
            "repair_reason": "",
            "repaired_guard_passed": False,
            "execution_success": False,
            "expected_tables_met": False,
            "required_fragments_met": False,
            "forbidden_fragments_absent": False,
            "intent_preserved": False,
            "end_to_end_success": False,
            "execution_time_ms": 0,
            "error": None,
        }


async def main_async() -> None:
    """CLI 入口：运行完整 Repair 评测并写入独立报告。"""
    runner = RepairEvaluationRunner()
    report = await runner.evaluate_all()
    RepairReportWriter().write(report)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
