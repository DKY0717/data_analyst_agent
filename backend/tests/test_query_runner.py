# Query Runner 测试文件
import pytest
from contextlib import contextmanager

from app.db import query_runner as query_runner_module
from app.db.query_runner import QueryRunner

def test_query_runner_execute_select():
    """测试SELECT查询成功执行"""
    runner = QueryRunner()
    result = runner.execute("SELECT 1 as test")
    assert result["success"] == True
    assert "columns" in result
    assert "rows" in result

def test_query_runner_execution_time():
    """测试返回执行时间"""
    runner = QueryRunner()
    result = runner.execute("SELECT 1 as test")
    assert "execution_time_ms" in result
    assert isinstance(result["execution_time_ms"], (int, float))

def test_query_runner_error_handling():
    """测试查询不存在的表时返回错误"""
    runner = QueryRunner()
    result = runner.execute("SELECT * FROM non_existent_table")
    assert result["success"] == False
    assert "error" in result


def test_query_runner_keeps_sandbox_diagnostic_private_for_repair():
    """公开错误保持泛化，内部修复链仍可取得数据库诊断。"""
    runner = QueryRunner(timeout=5, sandbox=True)

    result = runner.execute("SELECT * FROM non_existent_table")

    assert result["success"] is False
    assert result["error"] == "查询执行失败"
    assert "non_existent_table" not in result["error"]
    assert "non_existent_table" in result["diagnostic_error"]
    assert result["execution_mode"] == "sandbox"


def test_query_runner_reads_sandbox_mode_from_settings(monkeypatch):
    """测试默认执行模式跟随配置，避免 SANDBOX_MODE 只停留在注释里。"""
    monkeypatch.setattr(query_runner_module.settings, "SANDBOX_MODE", True, raising=False)

    runner = QueryRunner()

    assert runner.sandbox is True


def test_query_runner_explicit_sandbox_argument_overrides_settings(monkeypatch):
    """测试显式传参仍可覆盖配置，便于单测和局部调试精确控制执行模式。"""
    monkeypatch.setattr(query_runner_module.settings, "SANDBOX_MODE", True, raising=False)

    runner = QueryRunner(sandbox=False)

    assert runner.sandbox is False


def test_query_runner_passes_postgresql_settings_to_sandbox(monkeypatch):
    """测试 PostgreSQL 沙箱使用真实 PG 连接配置，而不是误传 DuckDB 文件路径。"""
    captured = {}
    monkeypatch.setattr(query_runner_module.db_connection, "backend", "postgresql")
    monkeypatch.setattr(query_runner_module.settings, "PG_HOST", "pg.local")
    monkeypatch.setattr(query_runner_module.settings, "PG_PORT", 15432)
    monkeypatch.setattr(query_runner_module.settings, "PG_USER", "analyst")
    monkeypatch.setattr(query_runner_module.settings, "PG_PASSWORD", "secret")
    monkeypatch.setattr(query_runner_module.settings, "PG_DATABASE", "warehouse")

    def fake_execute(sql, connection_config, backend, timeout=None, include_diagnostics=False):
        captured["sql"] = sql
        captured["connection_config"] = connection_config
        captured["backend"] = backend
        captured["timeout"] = timeout
        captured["include_diagnostics"] = include_diagnostics
        return {"success": True, "columns": [], "rows": [], "execution_time_ms": 0, "row_count": 0}

    monkeypatch.setattr(query_runner_module.sandbox_executor, "execute", fake_execute)

    result = QueryRunner(sandbox=True).execute("SELECT 1")

    assert result["success"] is True
    assert captured["backend"] == "postgresql"
    assert captured["timeout"] == query_runner_module.settings.SQL_TIMEOUT
    assert captured["include_diagnostics"] is True
    assert captured["connection_config"] == {
        "host": "pg.local",
        "port": 15432,
        "user": "analyst",
        "password": "secret",
        "dbname": "warehouse",
    }


def test_postgresql_direct_execution_sets_transaction_local_statement_timeout(monkeypatch):
    """PostgreSQL 直连也必须由服务端事务超时兜底。"""
    calls = []

    class FakeCursor:
        description = [("value",)]

        def execute(self, sql, params=None):
            calls.append((sql, params))

        def fetchall(self):
            return [(1,)]

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    @contextmanager
    def fake_session():
        yield FakeConnection()

    monkeypatch.setattr(query_runner_module.db_connection, "backend", "postgresql")
    monkeypatch.setattr(query_runner_module.db_connection, "get_session", fake_session)

    result = QueryRunner(timeout=7, sandbox=False).execute("SELECT 1")

    assert result["success"] is True
    assert calls == [
        ("SELECT set_config('statement_timeout', %s, true)", ("7s",)),
        ("SELECT 1", None),
    ]
    assert result["execution_mode"] == "direct"
