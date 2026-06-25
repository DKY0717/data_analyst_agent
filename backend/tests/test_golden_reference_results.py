"""黄金参考 SQL 与固定业务断言的集成测试。"""

from pathlib import Path

import pytest
import yaml

from evaluation.reference_query_runner import reference_query_runner
from evaluation.result_comparator import result_comparator
from app.db.connection import db_connection


requires_duckdb = pytest.mark.skipif(
    db_connection.backend == "postgresql",
    reason="黄金参考 SQL 使用 DuckDB 方言，PostgreSQL 模式跳过",
)


CASE_FILE = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "cases"
    / "golden_result_cases.yaml"
)


def load_cases():
    """统一加载人工审核基准，保证三项集成断言使用同一批 case。"""
    with CASE_FILE.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)["cases"]


def run_reference(case):
    result = reference_query_runner.run(case["reference_sql"])
    assert result["guard_passed"] is True, case["id"]
    assert result["execution_success"] is True, case["id"]
    return result


@requires_duckdb
def test_all_golden_reference_queries_are_safe_and_executable():
    for case in load_cases():
        run_reference(case)


@requires_duckdb
def test_all_golden_fixed_assertions_pass_against_reference_results():
    for case in load_cases():
        reference_result = run_reference(case)
        comparison = result_comparator.compare(
            actual=reference_result,
            expected=reference_result,
            comparison=case["comparison"],
            fixed_assertions=case.get("fixed_assertions"),
        )

        assert comparison["fixed_assertions_matched"] is True, case["id"]
        assert comparison["result_correct"] is True, case["id"]


@requires_duckdb
def test_reference_result_columns_match_declared_required_columns():
    for case in load_cases():
        reference_result = run_reference(case)
        actual_columns = [column.casefold() for column in reference_result["columns"]]
        required_columns = [
            column.casefold() for column in case["comparison"]["required_columns"]
        ]

        assert actual_columns == required_columns, case["id"]
