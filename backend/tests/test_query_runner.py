# Query Runner 测试文件
import pytest
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
