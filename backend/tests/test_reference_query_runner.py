# ReferenceQueryRunner 测试
# 使用可注入的 fake 依赖，验证参考 SQL 始终先经过 Guard，且所有结果路径字段稳定。

from evaluation.reference_query_runner import ReferenceQueryRunner


RESULT_FIELDS = {
    "guard_passed",
    "execution_success",
    "columns",
    "rows",
    "row_count",
    "sanitized_sql",
    "error",
    "error_type",
}


class FakeGuard:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def validate(self, sql):
        self.calls.append(sql)
        if self.error:
            raise self.error
        return self.result


class FakeQueryRunner:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def execute(self, sql):
        self.calls.append(sql)
        if self.error:
            raise self.error
        return self.result


def test_reference_runner_validates_and_executes_only_sanitized_sql():
    guard = FakeGuard(
        {
            "is_safe": True,
            "sanitized_sql": "SELECT 1 AS value LIMIT 1000",
            "reason": None,
        }
    )
    query = FakeQueryRunner(
        {
            "success": True,
            "columns": ["value"],
            "rows": [[1]],
            "row_count": 1,
            "execution_time_ms": 2,
        }
    )

    result = ReferenceQueryRunner(guard=guard, query_runner=query).run("SELECT 1 AS value")

    assert set(result) == RESULT_FIELDS
    assert result == {
        "guard_passed": True,
        "execution_success": True,
        "columns": ["value"],
        "rows": [[1]],
        "row_count": 1,
        "sanitized_sql": "SELECT 1 AS value LIMIT 1000",
        "error": None,
        "error_type": None,
    }
    assert guard.calls == ["SELECT 1 AS value"]
    assert query.calls == ["SELECT 1 AS value LIMIT 1000"]


def test_reference_runner_does_not_execute_blocked_sql():
    guard = FakeGuard(
        {
            "is_safe": False,
            "sanitized_sql": "DROP TABLE orders",
            "reason": "禁止的语句类型",
        }
    )
    query = FakeQueryRunner()

    result = ReferenceQueryRunner(guard=guard, query_runner=query).run("DROP TABLE orders")

    assert set(result) == RESULT_FIELDS
    assert result["guard_passed"] is False
    assert result["execution_success"] is False
    assert result["columns"] == []
    assert result["rows"] == []
    assert result["row_count"] == 0
    assert result["sanitized_sql"] == "DROP TABLE orders"
    assert result["error"] == "禁止的语句类型"
    assert result["error_type"] == "reference_guard_blocked"
    assert query.calls == []


def test_reference_runner_returns_stable_execution_failure():
    sanitized_sql = "SELECT missing FROM orders LIMIT 1000"
    guard = FakeGuard({"is_safe": True, "sanitized_sql": sanitized_sql, "reason": None})
    query = FakeQueryRunner(
        {
            "success": False,
            "columns": [],
            "rows": [],
            "error": "column missing not found",
            "error_type": "BinderException",
        }
    )

    result = ReferenceQueryRunner(guard=guard, query_runner=query).run("SELECT missing FROM orders")

    assert set(result) == RESULT_FIELDS
    assert result["guard_passed"] is True
    assert result["execution_success"] is False
    assert result["columns"] == []
    assert result["rows"] == []
    assert result["row_count"] == 0
    assert result["sanitized_sql"] == sanitized_sql
    assert result["error"] == "column missing not found"
    assert result["error_type"] == "reference_execution_failed"


def test_reference_runner_captures_unexpected_guard_exception():
    guard = FakeGuard(error=RuntimeError("guard unavailable"))
    query = FakeQueryRunner()

    result = ReferenceQueryRunner(guard=guard, query_runner=query).run("SELECT 1")

    assert set(result) == RESULT_FIELDS
    assert result["guard_passed"] is False
    assert result["execution_success"] is False
    assert result["sanitized_sql"] == ""
    assert result["error"] == "guard unavailable"
    assert result["error_type"] == "reference_unexpected_error"
    assert query.calls == []


def test_reference_runner_captures_unexpected_executor_exception():
    sanitized_sql = "SELECT 1 LIMIT 1000"
    guard = FakeGuard({"is_safe": True, "sanitized_sql": sanitized_sql, "reason": None})
    query = FakeQueryRunner(error=RuntimeError("database unavailable"))

    result = ReferenceQueryRunner(guard=guard, query_runner=query).run("SELECT 1")

    assert set(result) == RESULT_FIELDS
    assert result["guard_passed"] is True
    assert result["execution_success"] is False
    assert result["sanitized_sql"] == sanitized_sql
    assert result["error"] == "database unavailable"
    assert result["error_type"] == "reference_unexpected_error"
    assert query.calls == [sanitized_sql]
