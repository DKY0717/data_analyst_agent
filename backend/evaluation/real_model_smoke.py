"""真实 OpenAI-compatible 模型核心 smoke 评测。"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.agents.graph import get_agent_graph
from evaluation.core_path import CorePathCase, CorePathCaseLoader


SMOKE_CASE_IDS = (
    "monthly_sales_demo",
    "category_refund_rate_demo",
    "payment_method_sales_demo",
    "analyst_customer_name_block_demo",
)

AgentRunner = Callable[..., Awaitable[dict[str, Any]]]


class RealModelSmokeRunner:
    """用真实模型跑少量高价值路径，完整评测前快速暴露配置或契约失败。"""

    def __init__(
        self,
        agent_runner: AgentRunner | None = None,
        cases: list[CorePathCase] | None = None,
    ):
        all_cases = CorePathCaseLoader().load_cases()
        case_map = {case.case_id: case for case in all_cases}
        self.cases = cases or [case_map[case_id] for case_id in SMOKE_CASE_IDS]
        self.agent_runner = agent_runner or get_agent_graph().run

    async def evaluate_all(self) -> dict[str, Any]:
        results = []
        for case in self.cases:
            results.append(await self._evaluate_case(case))
        passed_cases = sum(result["passed"] for result in results)
        return {
            "summary": {
                "total_cases": len(results),
                "passed_cases": passed_cases,
                "passed": bool(results) and passed_cases == len(results),
            },
            "results": results,
        }

    async def _evaluate_case(self, case: CorePathCase) -> dict[str, Any]:
        try:
            state = await self.agent_runner(
                case.question,
                session_id=f"real-smoke:{case.case_id}",
                auth_user={
                    "user_id": f"real-smoke:{case.demo_role or 'admin'}",
                    "auth_method": "evaluation",
                    "roles": [case.demo_role or "admin"],
                },
            )
            actual_status = state.get("status", "completed")
            audit = state.get("audit_report") or {}
            blocked_rules = list(audit.get("blocked_rules") or [])
            status_matched = actual_status == case.expected_status
            rule_matched = (
                case.expected_blocked_rule is None
                or case.expected_blocked_rule in blocked_rules
            )
            execution_matched = (
                state.get("execution_success") is True
                if case.expected_status == "completed"
                else True
            )
            passed = status_matched and rule_matched and execution_matched
            return {
                "case_id": case.case_id,
                "expected_status": case.expected_status,
                "actual_status": actual_status,
                "blocked_rules": blocked_rules,
                "execution_success": bool(state.get("execution_success")),
                "row_count": int((state.get("query_result") or {}).get("row_count") or 0),
                "failure_stage": None if passed else self._failure_stage(state),
                "passed": passed,
            }
        except Exception as exc:
            result = {
                "case_id": case.case_id,
                "expected_status": case.expected_status,
                "actual_status": "error",
                "blocked_rules": [],
                "execution_success": False,
                "row_count": 0,
                "failure_stage": "unexpected_error",
                "error_type": type(exc).__name__,
                "passed": False,
            }
            # LLM 调用边界已完成字符白名单清洗；smoke 只复制结构化元数据，不写异常 message。
            provider_fields = {
                "provider_status_code": getattr(exc, "status_code", None),
                "provider_error_code": getattr(exc, "provider_code", None),
                "provider_error_type": getattr(exc, "provider_type", None),
            }
            result.update(
                {key: value for key, value in provider_fields.items() if value is not None}
            )
            return result

    @staticmethod
    def _failure_stage(state: dict[str, Any]) -> str:
        if state.get("intent_is_safe") is False:
            return "intent_guard"
        if state.get("status") == "clarification_required":
            return "clarification"
        if state.get("is_sql_safe") is False:
            return "sql_guard"
        if state.get("permission_allowed") is False:
            return "permission"
        if state.get("execution_success") is False:
            return "execution"
        return "contract"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行真实模型核心 smoke")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = asyncio.run(RealModelSmokeRunner().evaluate_all())
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
