# SQL Repair 故障注入 case 测试
# 确保每条原始错误 SQL 都是可由 Guard 放行、但会在数据库执行阶段失败的安全查询。

from pathlib import Path

import yaml

from app.security.sql_guard import sql_guard


CASE_FILE = Path(__file__).parents[1] / "evaluation" / "cases" / "sql_repair_cases.yaml"


def load_cases():
    with CASE_FILE.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)["cases"]


def test_repair_evaluation_cases_define_six_deterministic_failures():
    cases = load_cases()

    assert len(cases) == 6
    assert len({case["id"] for case in cases}) == 6

    required_fields = {
        "id",
        "description",
        "original_sql",
        "expected_tables",
        "required_sql_fragments",
        "forbidden_sql_fragments",
    }
    assert all(required_fields <= case.keys() for case in cases)


def test_all_original_repair_sql_passes_guard_before_failure_injection():
    for case in load_cases():
        result = sql_guard.validate(case["original_sql"])
        assert result["is_safe"] is True, f"{case['id']}: {result['reason']}"
