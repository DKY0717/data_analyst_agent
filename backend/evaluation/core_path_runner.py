"""使用 Fake LLM + 真实 Agent/Guard/Permission/DuckDB 执行核心路径回归。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
import sqlglot
import yaml
from sqlglot import exp

from app.agents.answer_generator import AnswerGenerator
from app.agents.graph import AgentGraph
from app.agents.session_store import SQLiteSessionStore
from app.agents.sql_generator import SQLGenerator
from app.agents.sql_optimizer import SQLOptimizer
from app.analysis_intent.llm_parser import AnalysisIntentLLMParser
from app.analysis_intent.models import AnalysisIntent
from app.analysis_intent.rule_parser import AnalysisIntentRuleParser
from app.config import settings
from app.db.query_runner import QueryRunner
from app.db.schema_loader import SchemaLoader
from app.security.sql_guard import SQLGuard
from app.services.llm_observability import record_call
from evaluation.core_path import CorePathCase, CorePathCaseLoader
from evaluation.permission_evaluator import default_cases as permission_cases


class CorePathRunError(RuntimeError):
    """核心路径运行环境或 fixture 不完整。"""


class IsolatedDuckDBConnection:
    """为 Graph 提供临时只读 DuckDB 会话，避免改动项目数据库。"""

    backend = "duckdb"

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @contextmanager
    def get_session(self):
        connection = duckdb.connect(str(self.db_path), read_only=True)
        try:
            yield connection
        finally:
            connection.close()


class DeterministicLLM:
    """只替换外部模型边界，返回由现有评测资产提供的确定性结果。"""

    model = "deterministic-core-path-fixture"

    def __init__(self, sql_by_question: dict[str, str]):
        self.sql_by_question = sql_by_question
        self.rule_parser = AnalysisIntentRuleParser()

    async def parse_analysis_intent(self, question: str, semantic_context: str) -> dict[str, Any]:
        started_at = time.perf_counter()
        intent = self.rule_parser.parse(question)
        if intent.missing_slots and question.strip() != "帮我分析一下":
            # 明细查询没有聚合指标；Fake LLM 明确识别为 lookup，避免规则层误触发澄清。
            intent = AnalysisIntent(
                task_types=["lookup"],
                missing_slots=[],
                overall_confidence=0.95,
            )
        self._record("parse_analysis_intent", started_at)
        return intent.model_dump()

    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        conversation_context: str = "",
        analysis_intent: str = "",
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        sql = self.sql_by_question.get(question)
        if sql is None:
            raise CorePathRunError("missing deterministic SQL fixture")
        tables = sorted({
            table.name.lower()
            for table in sqlglot.parse_one(sql, dialect="duckdb").find_all(exp.Table)
            if table.name
        })
        self._record("generate_sql", started_at)
        return {
            "sql": sql,
            "tables": tables,
            "explanation": "deterministic core-path fixture",
        }

    async def generate_answer(
        self,
        question: str,
        sql: str,
        query_result: dict[str, Any],
    ) -> str:
        started_at = time.perf_counter()
        self._record("generate_answer", started_at)
        return f"确定性核心路径执行成功，共返回 {query_result.get('row_count', 0)} 行。"

    def _record(self, stage: str, started_at: float) -> None:
        record_call(
            {
                "stage": stage,
                "model": self.model,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "latency_ms": max(0, int((time.perf_counter() - started_at) * 1000)),
                "attempt_count": 1,
                "estimated_cost": 0.0,
                "success": True,
                "error_type": None,
            }
        )


class CorePathRunner:
    """执行核心路径，并输出可定位阶段和缺失 surface 的稳定结果。"""

    def __init__(
        self,
        cases: list[CorePathCase] | None = None,
        source_database: str | Path | None = None,
        sql_overrides: dict[str, str] | None = None,
    ):
        loader = CorePathCaseLoader()
        self.cases = cases or loader.load_cases()
        self.case_version = loader.load_version()
        self.source_database = Path(
            source_database or settings.DATA_DIR / "database.duckdb"
        )
        self.sql_overrides = sql_overrides or {}
        self._cases_by_id = {case.case_id: case for case in self.cases}
        self._golden_cases = self._load_golden_cases()
        self._permission_cases = {case.case_id: case for case in permission_cases()}

    async def evaluate_all(self) -> dict[str, Any]:
        """在单份临时数据库副本上顺序执行，单 case 失败不终止整批。"""
        if not self.source_database.exists():
            raise CorePathRunError("source DuckDB does not exist; run seed_data first")

        previous_policy_path = os.environ.pop("DATA_PERMISSION_POLICY_PATH", None)
        try:
            with tempfile.TemporaryDirectory(prefix="core-path-") as temp_dir:
                isolated_path = Path(temp_dir) / "core-path.duckdb"
                shutil.copy2(self.source_database, isolated_path)
                results = [
                    await self._evaluate_case(case, isolated_path, Path(temp_dir))
                    for case in self.cases
                ]
        finally:
            if previous_policy_path is not None:
                os.environ["DATA_PERMISSION_POLICY_PATH"] = previous_policy_path

        passed = sum(result["passed"] for result in results)
        return {
            "metadata": {
                "case_version": self.case_version,
                "llm_mode": "deterministic_fixture",
                "agent_graph": "real",
                "database_mode": "isolated_duckdb_copy",
            },
            "summary": {
                "total_cases": len(results),
                "passed_cases": passed,
                "pass_rate": passed / len(results) if results else 0.0,
                "surface_completeness_rate": self._surface_rate(results),
                "passed": bool(results) and passed == len(results),
            },
            "results": results,
        }

    async def _evaluate_case(
        self,
        case: CorePathCase,
        database_path: Path,
        temp_dir: Path,
    ) -> dict[str, Any]:
        """构造 case 专属 Fake LLM，其他依赖全部使用真实实现。"""
        session_store = SQLiteSessionStore(
            db_path=str(temp_dir / f"sessions-{case.case_id}.db")
        )
        try:
            sql_by_question = self._sql_fixtures_for(case)
            fake_llm = DeterministicLLM(sql_by_question)
            connection = IsolatedDuckDBConnection(database_path)
            query_runner = QueryRunner(timeout=5, sandbox=False, connection=connection)
            graph = AgentGraph(
                llm_parser=AnalysisIntentLLMParser(client=fake_llm),
                sql_generator_service=SQLGenerator(client=fake_llm),
                answer_generator_service=AnswerGenerator(client=fake_llm),
                schema_loader_service=SchemaLoader(db=connection),
                query_runner_service=query_runner,
                sql_optimizer_service=SQLOptimizer(
                    query_runner_service=query_runner,
                    sql_guard_service=SQLGuard(max_rows=settings.SQL_MAX_ROWS),
                ),
                session_store_service=session_store,
            )
            session_id = f"core-path:{case.case_id}"
            if case.setup_case_id:
                setup_case = self._cases_by_id[case.setup_case_id]
                setup_state = await graph.run(
                    setup_case.question,
                    session_id=session_id,
                    auth_user=self._auth_user(case.demo_role),
                )
                if setup_state.get("execution_success") is not True:
                    return self._result(case, setup_state, "setup_failed")

            state = await graph.run(
                case.question,
                session_id=session_id,
                auth_user=self._auth_user(case.demo_role),
            )
            return self._result(case, state)
        except Exception as exc:
            return {
                "case_id": case.case_id,
                "category": case.category,
                "expected_status": case.expected_status,
                "actual_status": "error",
                "status_matched": False,
                "expected_blocked_rule": case.expected_blocked_rule,
                "actual_blocked_rules": [],
                "blocked_rule_matched": False,
                "failure_stage": "unexpected_error",
                "error_type": type(exc).__name__,
                "missing_surfaces": list(case.expected_surfaces),
                "surface_results": {
                    surface: False for surface in case.expected_surfaces
                },
                "columns": [],
                "row_count": 0,
                "passed": False,
            }
        finally:
            session_store.close()

    def _result(
        self,
        case: CorePathCase,
        state: dict[str, Any],
        forced_failure_stage: str | None = None,
    ) -> dict[str, Any]:
        actual_status = state.get("status", "completed")
        audit_report = state.get("audit_report") or {}
        blocked_rules = list(audit_report.get("blocked_rules") or [])
        surface_results = {
            surface: self._surface_available(surface, state, audit_report)
            for surface in case.expected_surfaces
        }
        missing_surfaces = [
            surface for surface, available in surface_results.items() if not available
        ]
        status_matched = actual_status == case.expected_status
        rule_matched = (
            case.expected_blocked_rule is None
            or case.expected_blocked_rule in blocked_rules
        )
        passed = (
            forced_failure_stage is None
            and status_matched
            and rule_matched
            and not missing_surfaces
        )
        failure_stage = forced_failure_stage
        if failure_stage is None and not passed:
            failure_stage = self._failure_stage(
                state,
                status_matched,
                rule_matched,
                missing_surfaces,
            )
        query_result = state.get("query_result") or {}
        return {
            "case_id": case.case_id,
            "category": case.category,
            "expected_status": case.expected_status,
            "actual_status": actual_status,
            "status_matched": status_matched,
            "expected_blocked_rule": case.expected_blocked_rule,
            "actual_blocked_rules": blocked_rules,
            "blocked_rule_matched": rule_matched,
            "failure_stage": failure_stage,
            "error_type": state.get("execution_error_type"),
            "missing_surfaces": missing_surfaces,
            "surface_results": surface_results,
            "columns": list(query_result.get("columns") or []),
            "row_count": int(query_result.get("row_count") or 0),
            "passed": passed,
        }

    def _sql_fixtures_for(self, case: CorePathCase) -> dict[str, str]:
        fixtures = {case.question: self._sql_for_case(case)} if self._needs_sql(case) else {}
        if case.setup_case_id:
            setup_case = self._cases_by_id[case.setup_case_id]
            fixtures[setup_case.question] = self._sql_for_case(setup_case)
        return fixtures

    def _sql_for_case(self, case: CorePathCase) -> str:
        if case.case_id in self.sql_overrides:
            return self.sql_overrides[case.case_id]
        for link in case.linked_cases:
            if link["source"] == "golden_result":
                return str(self._golden_cases[link["id"]]["reference_sql"]).strip()
            if link["source"] == "permission":
                return self._permission_cases[link["id"]].sql
        raise CorePathRunError("executable case has no SQL fixture link")

    @staticmethod
    def _needs_sql(case: CorePathCase) -> bool:
        return case.expected_status not in {"clarification_required"} and case.category != "safety_failure"

    @staticmethod
    def _auth_user(role: str | None) -> dict[str, Any]:
        return {
            "user_id": f"core-path:{role or 'admin'}",
            "auth_method": "evaluation",
            "roles": [role or "admin"],
        }

    @staticmethod
    def _surface_available(
        surface: str,
        state: dict[str, Any],
        audit_report: dict[str, Any],
    ) -> bool:
        query_result = state.get("query_result") or {}
        permission = audit_report.get("permission_observability") or {}
        blocked_rules = list(audit_report.get("blocked_rules") or [])
        checks = {
            "answer": bool(state.get("answer")) and state.get("execution_success") is True,
            "blocked_answer": bool(state.get("answer")) and state.get("status") == "blocked",
            "sql": bool(state.get("validated_sql") or state.get("generated_sql")),
            "chart": bool(query_result.get("rows")) and len(query_result.get("columns") or []) >= 2,
            "table": bool(query_result.get("columns")) and bool(query_result.get("rows")),
            "audit_report": bool(audit_report.get("events")),
            "permission_observability": permission.get("permission_checked") is True,
            "row_filter_region_scope": any(
                item.get("rule_id") == "row_filter_region_scope"
                for item in permission.get("row_filters_applied") or []
            ),
            "blocked_rules": bool(blocked_rules),
            "session_context": bool(state.get("conversation_context")),
            "clarification": bool(state.get("clarification_request")),
        }
        if surface.startswith("block_"):
            return surface in blocked_rules
        return bool(checks.get(surface, False))

    @staticmethod
    def _failure_stage(
        state: dict[str, Any],
        status_matched: bool,
        rule_matched: bool,
        missing_surfaces: list[str],
    ) -> str:
        if state.get("intent_is_safe") is False:
            return "intent_guard"
        if state.get("status") == "clarification_required":
            return "clarification"
        if state.get("is_sql_safe") is False:
            return "sql_guard"
        if state.get("permission_allowed") is False:
            return "permission"
        if state.get("execution_success") is False and state.get("query_result"):
            return "execution"
        if not status_matched:
            return "status_mismatch"
        if not rule_matched:
            return "blocked_rule_mismatch"
        if missing_surfaces:
            return "surface_incomplete"
        return "unknown"

    @staticmethod
    def _surface_rate(results: list[dict[str, Any]]) -> float:
        surfaces = [
            value
            for result in results
            for value in result.get("surface_results", {}).values()
        ]
        return sum(bool(value) for value in surfaces) / len(surfaces) if surfaces else 0.0

    @staticmethod
    def _load_golden_cases() -> dict[str, dict[str, Any]]:
        case_file = Path(__file__).parent / "cases" / "golden_result_cases.yaml"
        payload = yaml.safe_load(case_file.read_text(encoding="utf-8"))
        return {case["id"]: case for case in payload["cases"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行可执行核心路径确定性回归")
    parser.add_argument("--output", help="可选 JSON 报告路径")
    parser.add_argument("--database", help="源 DuckDB 路径")
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(CorePathRunner(source_database=args.database).evaluate_all())
    except (CorePathRunError, OSError, yaml.YAMLError):
        return 2

    if args.output:
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
