# SQL Guard 测试文件
import pytest
from app.security.sql_guard import SQLGuard

def test_sql_guard_select_safe():
    """测试SELECT语句是安全的"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM orders")
    assert result["is_safe"] == True

def test_sql_guard_blocks_empty_sql_with_clear_reason():
    """模型拒绝危险请求并返回空 SQL 时，应给出明确阻断原因"""
    guard = SQLGuard()
    result = guard.validate("   ")
    assert result["is_safe"] == False
    assert result["reason"] == "SQL 为空"
    assert result["blocked_rule"] == "block_empty_sql"

def test_sql_guard_drop_unsafe():
    """测试DROP语句是不安全的"""
    guard = SQLGuard()
    result = guard.validate("DROP TABLE orders")
    assert result["is_safe"] == False

def test_sql_guard_delete_unsafe():
    """测试DELETE语句是不安全的"""
    guard = SQLGuard()
    result = guard.validate("DELETE FROM orders")
    assert result["is_safe"] == False

def test_sql_guard_update_unsafe():
    """测试UPDATE语句是不安全的"""
    guard = SQLGuard()
    result = guard.validate("UPDATE orders SET status='x'")
    assert result["is_safe"] == False

def test_sql_guard_insert_unsafe():
    """测试INSERT语句是不安全的"""
    guard = SQLGuard()
    result = guard.validate("INSERT INTO orders VALUES (1, 2)")
    assert result["is_safe"] == False

def test_sql_guard_multi_statement_unsafe():
    """测试多语句是不安全的"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM orders; DROP TABLE orders")
    assert result["is_safe"] == False

def test_sql_guard_with_cte_safe():
    """测试WITH CTE是安全的"""
    guard = SQLGuard()
    result = guard.validate("WITH t AS (SELECT * FROM orders) SELECT * FROM t")
    assert result["is_safe"] == True

def test_sql_guard_add_limit():
    """测试自动添加LIMIT"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM orders")
    assert "LIMIT" in result["sanitized_sql"].upper()
    assert result["limit_injected"] is True
    assert any(event["action"] == "inject_limit" for event in result["audit_events"])

def test_sql_guard_adds_limit_when_limit_only_appears_in_string_literal():
    """字符串里出现 LIMIT 不能骗过顶层 LIMIT 注入"""
    guard = SQLGuard()
    result = guard.validate("SELECT 'LIMIT' AS keyword_hint FROM orders")
    assert result["is_safe"] == True
    assert result["sanitized_sql"].upper().count("LIMIT") >= 2

def test_sql_guard_allows_explain_select():
    """允许 EXPLAIN SELECT，用于后续 SQL 优化分析"""
    guard = SQLGuard()
    result = guard.validate("EXPLAIN SELECT * FROM orders")
    assert result["is_safe"] == True
    assert result["limit_injected"] is False

def test_sql_guard_blocks_information_schema_access():
    """禁止查询系统 Schema，避免用户通过 Guard 枚举底层元数据"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM information_schema.tables")
    assert result["is_safe"] == False
    assert "系统表" in result["reason"]
    assert result["blocked_rule"] == "block_system_schema"
    assert result["audit_events"][0]["rule_id"] == "block_system_schema"
    assert result["audit_events"][0]["status"] == "blocked"

def test_sql_guard_blocks_pg_catalog_access():
    """禁止访问 PostgreSQL/DuckDB 兼容系统目录"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM pg_catalog.pg_tables")
    assert result["is_safe"] == False
    assert "系统表" in result["reason"]

def test_sql_guard_blocks_duckdb_system_function_access():
    """禁止调用 DuckDB 元数据函数，避免绕过系统表限制"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM duckdb_tables()")
    assert result["is_safe"] == False
    assert "危险函数" in result["reason"]
    assert result["blocked_rule"] == "block_dangerous_function"

def test_sql_guard_blocks_file_read_functions():
    """禁止 DuckDB 文件读取函数，防止通过 SELECT 读取本机文件"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM read_csv_auto('/etc/passwd')")
    assert result["is_safe"] == False
    assert "危险函数" in result["reason"]
    assert result["blocked_rule"] == "block_dangerous_function"
