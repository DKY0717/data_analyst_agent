# SQL Guard 测试文件
import pytest
from app.security.sql_guard import SQLGuard

def test_sql_guard_select_safe():
    """测试SELECT语句是安全的"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM orders")
    assert result["is_safe"] == True

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