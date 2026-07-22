# SQL 沙箱测试

import tempfile
import os
import json
import duckdb
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.db._sandbox_worker import _json_default
from app.db.sandbox import SandboxExecutor


def test_sandbox_worker_serializes_supported_database_scalars():
    assert _json_default(date(2026, 7, 11)) == "2026-07-11"
    assert _json_default(datetime(2026, 7, 11, 8, 30)) == "2026-07-11T08:30:00"
    assert _json_default(Decimal("12.34")) == 12.34


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
    assert result["error"] == "查询执行失败"
    assert "nonexistent_table" not in repr(result)

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


def test_sandbox_unexpected_error_is_sanitized(monkeypatch):
    """子进程启动异常可能包含路径或凭据，对外错误必须稳定泛化。"""
    from app.db import sandbox as sandbox_module

    def fail_run(*args, **kwargs):
        raise OSError("password=private /secret/worker/path")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fail_run)

    result = SandboxExecutor(timeout=1).execute("SELECT 1", "unused.duckdb", "duckdb")

    assert result["success"] is False
    assert result["error"] == "沙箱执行失败"
    assert "private" not in repr(result)


def test_sandbox_uses_requested_timeout_as_hard_process_deadline(monkeypatch):
    """QueryRunner 配置的 SQL_TIMEOUT 必须成为真实进程截止时间。"""
    from app.db import sandbox as sandbox_module

    captured = {}

    def fake_run(*args, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"success": True, "columns": [], "rows": [], "row_count": 0}),
            stderr="",
        )

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)

    result = SandboxExecutor(timeout=30).execute(
        "SELECT 1",
        "unused.duckdb",
        "duckdb",
        timeout=3,
    )

    assert result["success"] is True
    assert captured["timeout"] == 3
