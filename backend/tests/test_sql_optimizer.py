# SQL Optimizer 测试
# 目标：让“优化建议”成为可验证的真实能力，而不是 API 响应里的空字段

from unittest.mock import patch

from app.agents.sql_optimizer import SQLOptimizer


def make_explain_result(plan_text: str):
    """构造 DuckDB EXPLAIN 的查询结果，模拟 QueryRunner 返回结构。"""
    return {
        "success": True,
        "columns": ["explain_key", "explain_value"],
        "rows": [["physical_plan", plan_text]],
        "execution_time_ms": 2,
        "row_count": 1,
    }


def test_optimizer_suggests_explicit_columns_for_select_star():
    """SELECT * 会增加不必要的数据读取，应建议只选择需要字段。"""
    optimizer = SQLOptimizer()
    query_result = {"success": True, "rows": [[1]], "row_count": 1, "execution_time_ms": 5}

    with patch("app.agents.sql_optimizer.query_runner") as mock_runner:
        mock_runner.execute.return_value = make_explain_result("SEQ_SCAN orders")
        suggestions = optimizer.optimize("SELECT * FROM orders LIMIT 1000", query_result)

    assert any("避免使用 SELECT *" in item for item in suggestions)


def test_optimizer_suggests_filtering_when_result_hits_limit():
    """结果行数达到上限时，应提示用户增加筛选条件或缩小分析范围。"""
    optimizer = SQLOptimizer(max_rows=2)
    query_result = {
        "success": True,
        "rows": [[1], [2]],
        "row_count": 2,
        "execution_time_ms": 8,
    }

    with patch("app.agents.sql_optimizer.query_runner") as mock_runner:
        mock_runner.execute.return_value = make_explain_result("SEQ_SCAN orders")
        suggestions = optimizer.optimize("SELECT order_id FROM orders LIMIT 2", query_result)

    assert any("结果达到返回上限" in item for item in suggestions)


def test_optimizer_uses_safe_explain_before_query_plan():
    """生成执行计划前必须再次走 SQL Guard，不能直接执行拼接后的 EXPLAIN。"""
    optimizer = SQLOptimizer()
    query_result = {"success": True, "rows": [[1]], "row_count": 1, "execution_time_ms": 5}

    with patch("app.agents.sql_optimizer.sql_guard") as mock_guard, \
         patch("app.agents.sql_optimizer.query_runner") as mock_runner:
        mock_guard.validate.return_value = {
            "is_safe": True,
            "sanitized_sql": "EXPLAIN SELECT order_id FROM orders LIMIT 1000",
            "reason": None,
        }
        mock_runner.execute.return_value = make_explain_result("SEQ_SCAN orders")

        optimizer.optimize("SELECT order_id FROM orders LIMIT 1000", query_result)

    mock_guard.validate.assert_called_once_with("EXPLAIN SELECT order_id FROM orders LIMIT 1000")
    mock_runner.execute.assert_called_once_with("EXPLAIN SELECT order_id FROM orders LIMIT 1000")
