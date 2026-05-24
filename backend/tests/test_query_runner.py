# Query Runner 测试文件
import pytest
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
