"""数据权限 SQL 改写与真实 DuckDB 执行集成测试。"""

from app.db.query_runner import QueryRunner
from app.db.schema_loader import schema_loader
from app.security.data_permission import DataPermissionGuard
from app.security.sql_guard import SQLGuard


def test_authorized_multi_table_sql_is_unambiguous_safe_and_executable(monkeypatch):
    """行过滤改写后要再次通过 Guard，并由真实数据库证明没有歧义。"""
    monkeypatch.delenv("DATA_PERMISSION_POLICY_PATH", raising=False)
    sql = (
        "SELECT o.order_id, c.region_id "
        "FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
        "ORDER BY o.order_id LIMIT 1000"
    )
    schema = schema_loader.get_full_schema()

    initial_guard = SQLGuard(max_rows=1000).validate(sql)
    permission = DataPermissionGuard().authorize(
        initial_guard["sanitized_sql"],
        {"user_id": "analyst:test", "auth_method": "jwt", "roles": ["analyst"]},
        schema,
    )
    final_guard = SQLGuard(max_rows=1000).validate(permission.authorized_sql)
    execution = QueryRunner(timeout=5, sandbox=False).execute(final_guard["sanitized_sql"])

    assert initial_guard["is_safe"] is True
    assert permission.is_allowed is True
    assert "o.customer_id IN" in permission.authorized_sql
    assert final_guard["is_safe"] is True
    assert execution["success"] is True
    assert execution["rows"]
    assert {row[1] for row in execution["rows"]} <= {1, 2}
