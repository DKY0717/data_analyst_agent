# SQL 沙箱测试

import tempfile
import os
import json
import duckdb
from pathlib import Path

from app.db.sandbox import SandboxExecutor


def test_sandbox_execute_select():
    """沙箱执行简单 SELECT"""
    db_path = tempfile.mktemp(suffix=".duckdb")
    conn = duckdb.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER, name VARCHAR)")
    conn.execute("INSERT INTO t VALUES (1, 'test')")
    conn.close()

    executor = SandboxExecutor(timeout=10)
    result = executor.execute("SELECT * FROM t", db_path, "duckdb")

    assert result["success"] is True
    assert result["columns"] == ["id", "name"]
    assert result["rows"] == [[1, "test"]]

    os.unlink(db_path)


def test_sandbox_execute_invalid_sql():
    """沙箱处理无效 SQL"""
    db_path = tempfile.mktemp(suffix=".duckdb")
    conn = duckdb.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.close()

    executor = SandboxExecutor(timeout=10)
    result = executor.execute("SELECT * FROM nonexistent_table", db_path, "duckdb")

    assert result["success"] is False
    assert "error" in result

    os.unlink(db_path)


def test_sandbox_process_isolation():
    """沙箱子进程崩溃不影响主进程"""
    db_path = tempfile.mktemp(suffix=".duckdb")

    executor = SandboxExecutor(timeout=5)
    result = executor.execute("INVALID SQL ???", db_path, "duckdb")

    # 主进程应该正常返回错误，而不是崩溃
    assert result["success"] is False
    assert "error" in result

    if os.path.exists(db_path):
        os.unlink(db_path)
