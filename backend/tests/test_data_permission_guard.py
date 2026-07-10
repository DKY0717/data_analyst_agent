# Data Permission Guard 测试
# 这些测试只验证 SQL AST 权限决策，不访问数据库或调用 LLM。

from pathlib import Path

from app.security.data_permission import DataPermissionGuard


def ecommerce_schema():
    """构造最小电商 Schema，覆盖权限策略涉及的表和字段。"""
    return {
        "tables": {
            "regions": {
                "columns": [
                    {"name": "region_id"},
                    {"name": "region_name"},
                    {"name": "province"},
                    {"name": "city"},
                ]
            },
            "customers": {
                "columns": [
                    {"name": "customer_id"},
                    {"name": "customer_name"},
                    {"name": "gender"},
                    {"name": "age"},
                    {"name": "region_id"},
                    {"name": "register_date"},
                ]
            },
            "orders": {
                "columns": [
                    {"name": "order_id"},
                    {"name": "customer_id"},
                    {"name": "order_date"},
                    {"name": "status"},
                    {"name": "total_amount"},
                ]
            },
            "order_items": {
                "columns": [
                    {"name": "item_id"},
                    {"name": "order_id"},
                    {"name": "product_id"},
                    {"name": "quantity"},
                    {"name": "unit_price"},
                ]
            },
            "payments": {
                "columns": [
                    {"name": "payment_id"},
                    {"name": "order_id"},
                    {"name": "payment_method"},
                    {"name": "payment_status"},
                    {"name": "paid_amount"},
                    {"name": "paid_at"},
                ]
            },
            "refunds": {
                "columns": [
                    {"name": "refund_id"},
                    {"name": "order_id"},
                    {"name": "refund_amount"},
                    {"name": "refund_reason"},
                    {"name": "refund_date"},
                ]
            },
        }
    }


def user(roles, auth_method="jwt"):
    return {"user_id": "user:test", "auth_method": auth_method, "roles": roles}


def normalize_sql(sql):
    return " ".join(sql.lower().split())


def test_dev_mode_without_user_allows_query_as_admin():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT customer_name FROM customers LIMIT 1000",
        None,
        ecommerce_schema(),
    )

    assert result.is_allowed is True
    assert result.blocked_rule is None
    assert result.audit_events[0]["details"]["auth_method"] == "disabled"
    assert result.audit_events[0]["details"]["roles"] == ["admin"]


def test_admin_can_access_sensitive_customer_field():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT c.customer_name FROM customers c LIMIT 1000",
        user(["admin"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is True
    assert "customers.customer_name" in result.referenced_columns


def test_admin_can_access_unknown_table_for_repair_flow():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT * FROM nonexistent_table LIMIT 1000",
        user(["admin"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is True
    assert result.referenced_tables == ["nonexistent_table"]


def test_analyst_can_access_order_sales_columns():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT SUM(o.total_amount) AS sales FROM orders o LIMIT 1000",
        user(["analyst"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is True
    assert result.referenced_tables == ["orders"]
    assert "orders.total_amount" in result.referenced_columns


def test_analyst_cannot_access_customer_name():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT c.customer_name FROM customers c LIMIT 1000",
        user(["analyst"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is False
    assert result.blocked_rule == "block_unauthorized_column"
    assert "customers.customer_name" in result.reason
    assert result.audit_events[0]["status"] == "blocked"


def test_analyst_cannot_select_star_from_restricted_customer_table():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT * FROM customers LIMIT 1000",
        user(["analyst"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is False
    assert result.blocked_rule == "block_unauthorized_column"
    assert "customers.*" in result.reason


def test_support_cannot_access_payment_amount():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT p.paid_amount FROM payments p LIMIT 1000",
        user(["support"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is False
    assert result.blocked_rule == "block_unauthorized_table"
    assert "payments" in result.reason


def test_unknown_role_denies_business_table():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT total_amount FROM orders LIMIT 1000",
        user(["guest"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is False
    assert result.blocked_rule == "block_unauthorized_table"


def test_multi_table_ambiguous_unqualified_column_fails_closed():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT order_id FROM orders JOIN payments ON orders.order_id = payments.order_id LIMIT 1000",
        user(["analyst"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is False
    assert result.blocked_rule == "block_ambiguous_column"
    assert "order_id" in result.reason


def test_projection_alias_in_order_by_is_not_treated_as_physical_column():
    """聚合别名已由底层表达式完成权限检查，ORDER BY 引用不应再次误判。"""
    guard = DataPermissionGuard()

    result = guard.authorize(
        (
            "SELECT p.product_name, "
            "SUM(oi.quantity * oi.unit_price) AS sales_amount "
            "FROM order_items oi JOIN products p ON oi.product_id = p.product_id "
            "GROUP BY p.product_name ORDER BY sales_amount DESC LIMIT 5"
        ),
        user(["analyst"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is True
    assert "order_items.quantity" in result.referenced_columns
    assert "order_items.unit_price" in result.referenced_columns
    assert all(not column.endswith(".sales_amount") for column in result.referenced_columns)


def test_single_table_unqualified_column_is_resolved_to_that_table():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT total_amount FROM orders LIMIT 1000",
        user(["analyst"]),
        ecommerce_schema(),
    )

    assert result.is_allowed is True
    assert result.referenced_columns == ["orders.total_amount"]


def test_authorization_event_contains_no_policy_dump():
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT total_amount FROM orders LIMIT 1000",
        {"user_id": "apikey:demo...", "auth_method": "api_key", "roles": ["user"]},
        ecommerce_schema(),
    )

    event = result.audit_events[0]
    assert result.is_allowed is True
    assert event["stage"] == "authorization"
    assert event["action"] == "authorize_sql"
    assert event["details"]["roles"] == ["analyst"]
    assert "ROLE_POLICIES" not in repr(event)
    assert "customers" not in event["details"]


def test_guard_uses_external_policy_file(tmp_path, monkeypatch):
    policy_path = Path(tmp_path) / "policy.yaml"
    policy_path.write_text(
        """
version: 1
roles:
  analyst:
    tables:
      orders:
        columns: ["order_id"]
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATA_PERMISSION_POLICY_PATH", str(policy_path))
    guard = DataPermissionGuard()

    allowed = guard.authorize("SELECT order_id FROM orders LIMIT 1000", user(["analyst"]), ecommerce_schema())
    blocked = guard.authorize("SELECT total_amount FROM orders LIMIT 1000", user(["analyst"]), ecommerce_schema())

    assert allowed.is_allowed is True
    assert blocked.is_allowed is False
    assert blocked.blocked_rule == "block_unauthorized_column"


def test_guard_fails_closed_when_configured_policy_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PERMISSION_POLICY_PATH", str(tmp_path / "missing.yaml"))
    guard = DataPermissionGuard()

    result = guard.authorize("SELECT total_amount FROM orders LIMIT 1000", user(["analyst"]), ecommerce_schema())

    assert result.is_allowed is False
    assert result.blocked_rule == "block_permission_policy_error"
    assert "权限策略加载失败" in result.reason


def test_analyst_order_query_returns_authorized_sql_with_row_filter(monkeypatch):
    monkeypatch.delenv("DATA_PERMISSION_POLICY_PATH", raising=False)
    guard = DataPermissionGuard()
    sql = "SELECT SUM(total_amount) AS sales FROM orders WHERE order_date >= DATE '2024-01-01' LIMIT 1000"

    result = guard.authorize(sql, user(["analyst"]), ecommerce_schema())

    normalized = normalize_sql(result.authorized_sql)
    assert result.is_allowed is True
    assert result.authorized_sql != sql
    assert "orders.customer_id in (select customer_id from customers where region_id in (1, 2))" in normalized
    assert result.row_filters_applied == [{"table": "orders", "rule_id": "row_filter_region_scope"}]
    assert result.audit_events[0]["rule_id"] == "row_filter_applied"
    assert result.audit_events[0]["details"]["authorized_sql_changed"] is True


def test_admin_order_query_keeps_authorized_sql_unchanged(monkeypatch):
    monkeypatch.delenv("DATA_PERMISSION_POLICY_PATH", raising=False)
    guard = DataPermissionGuard()
    sql = "SELECT SUM(total_amount) AS sales FROM orders LIMIT 1000"

    result = guard.authorize(sql, user(["admin"]), ecommerce_schema())

    assert result.is_allowed is True
    assert result.authorized_sql == sql
    assert result.row_filters_applied == []


def test_row_filter_uses_table_alias(monkeypatch):
    monkeypatch.delenv("DATA_PERMISSION_POLICY_PATH", raising=False)
    guard = DataPermissionGuard()

    result = guard.authorize(
        "SELECT SUM(o.total_amount) AS sales FROM orders o LIMIT 1000",
        user(["analyst"]),
        ecommerce_schema(),
    )

    normalized = normalize_sql(result.authorized_sql)
    assert result.is_allowed is True
    assert "o.customer_id in (select customer_id from customers where region_id in (1, 2))" in normalized


def test_row_filter_applies_to_every_alias_in_self_join(monkeypatch):
    """同一受限表出现多次时，每个读取别名都必须受到行过滤约束。"""
    monkeypatch.delenv("DATA_PERMISSION_POLICY_PATH", raising=False)
    guard = DataPermissionGuard()

    result = guard.authorize(
        (
            "SELECT left_o.order_id, right_o.order_id "
            "FROM orders left_o JOIN orders right_o "
            "ON left_o.customer_id = right_o.customer_id LIMIT 1000"
        ),
        user(["analyst"]),
        ecommerce_schema(),
    )

    normalized = normalize_sql(result.authorized_sql)
    assert result.is_allowed is True
    assert "left_o.customer_id in (select customer_id from customers" in normalized
    assert "right_o.customer_id in (select customer_id from customers" in normalized


def test_row_filter_audit_does_not_dump_expression(monkeypatch):
    monkeypatch.delenv("DATA_PERMISSION_POLICY_PATH", raising=False)
    guard = DataPermissionGuard()

    result = guard.authorize("SELECT total_amount FROM orders LIMIT 1000", user(["analyst"]), ecommerce_schema())

    details = result.audit_events[0]["details"]
    assert details["row_filters_applied"] == [{"table": "orders", "rule_id": "row_filter_region_scope"}]
    assert "SELECT customer_id FROM customers" not in repr(details)
