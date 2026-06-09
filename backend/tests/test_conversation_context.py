# 多轮上下文构建器测试
# 这些测试保证连续追问只复用“分析意图摘要”，不会把完整大结果塞进 LLM prompt。

from app.agents.conversation_context import ConversationContextBuilder


def make_final_state():
    return {
        "question": "统计 2024 年每个月销售额",
        "validated_sql": "SELECT month, SUM(total_amount) AS sales FROM orders GROUP BY month LIMIT 1000",
        "generated_sql": "SELECT month, SUM(total_amount) AS sales FROM orders GROUP BY month",
        "query_result": {
            "columns": ["month", "sales"],
            "rows": [["2024-01", 1000], ["2024-02", 1200]],
            "row_count": 2,
            "execution_time_ms": 18,
        },
        "answer": "2024 年 1 月销售额 1000，2 月销售额 1200。",
        "optimization_suggestions": ["建议增加时间过滤条件"],
    }


def test_extract_turn_keeps_analysis_summary_not_full_rows():
    builder = ConversationContextBuilder(answer_max_chars=12)

    turn = builder.extract_turn(make_final_state())

    assert turn["question"] == "统计 2024 年每个月销售额"
    assert turn["sql"].startswith("SELECT month")
    assert turn["columns"] == ["month", "sales"]
    assert turn["row_count"] == 2
    assert turn["answer_summary"].endswith("...")
    assert "1200" not in turn["answer_summary"]
    assert "rows" not in turn


def test_build_context_formats_recent_turns_for_prompt():
    builder = ConversationContextBuilder(max_turns=2)
    turns = [
        {"question": "第一轮", "sql": "SELECT 1", "columns": ["a"], "row_count": 1, "answer_summary": "旧结果"},
        {"question": "第二轮", "sql": "SELECT 2", "columns": ["b"], "row_count": 2, "answer_summary": "中间结果"},
        {"question": "第三轮", "sql": "SELECT 3", "columns": ["c"], "row_count": 3, "answer_summary": "最新结果"},
    ]

    context = builder.build_context(turns)

    assert "上一轮分析上下文" in context
    assert "第一轮" not in context
    assert "第二轮" in context
    assert "第三轮" in context
    assert "SELECT 3" in context
    assert "结果列: c" in context


def test_build_context_returns_empty_string_without_turns():
    builder = ConversationContextBuilder()

    assert builder.build_context([]) == ""
