"""可执行核心路径回归测试。"""

import hashlib

import pytest

from app.config import settings
from evaluation.core_path import CorePathCaseLoader
from evaluation.core_path_runner import CorePathRunError, CorePathRunner


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_all_core_paths_execute_with_real_graph_guards_permissions_and_duckdb():
    source_database = settings.DATA_DIR / "database.duckdb"
    before_hash = file_hash(source_database)

    report = await CorePathRunner(source_database=source_database).evaluate_all()

    assert report["metadata"] == {
        "case_version": "1.7",
        "llm_mode": "deterministic_fixture",
        "agent_graph": "real",
        "database_mode": "isolated_duckdb_copy",
    }
    assert report["summary"] == {
        "total_cases": 15,
        "passed_cases": 15,
        "pass_rate": 1.0,
        "surface_completeness_rate": 1.0,
        "passed": True,
    }
    assert {result["category"] for result in report["results"]} >= {
        "business_success",
        "business_metric",
        "follow_up",
        "permission",
        "safety_failure",
        "clarification",
    }
    assert all(result["failure_stage"] is None for result in report["results"])
    assert "rows" not in repr(report)
    assert file_hash(source_database) == before_hash


@pytest.mark.asyncio
async def test_core_path_failure_is_classified_at_sql_guard_stage():
    case = next(
        case
        for case in CorePathCaseLoader().load_cases()
        if case.case_id == "monthly_sales_demo"
    )

    report = await CorePathRunner(
        cases=[case],
        sql_overrides={"monthly_sales_demo": "DELETE FROM orders"},
    ).evaluate_all()
    result = report["results"][0]

    assert report["summary"]["passed"] is False
    assert result["actual_status"] == "blocked"
    assert result["failure_stage"] == "sql_guard"
    assert result["error_type"] is None


@pytest.mark.asyncio
async def test_core_path_runner_rejects_missing_source_database(tmp_path):
    with pytest.raises(CorePathRunError, match="source DuckDB"):
        await CorePathRunner(source_database=tmp_path / "missing.duckdb").evaluate_all()
