# 会话存储测试
# SQLiteSessionStore 是多轮分析的入口，测试重点是隔离 session、限制历史长度和生成上下文。

import tempfile
import os
from app.agents.session_store import SQLiteSessionStore


def make_state(question: str, sql: str = "SELECT 1"):
    return {
        "question": question,
        "validated_sql": sql,
        "is_sql_safe": True,
        "execution_success": True,
        "query_result": {
            "columns": ["value"],
            "rows": [[1]],
            "row_count": 1,
        },
        "answer": f"{question} 的结果",
        "optimization_suggestions": [],
    }


def make_store(max_turns=3):
    """创建临时数据库的存储实例，测试后自动清理"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = SQLiteSessionStore(max_turns=max_turns, db_path=path)
    return store


def test_append_turn_and_get_context():
    store = make_store()
    store.append_turn("session-1", make_state("统计销售额", "SELECT SUM(total_amount) FROM orders"))
    context = store.get_context("session-1")
    assert "统计销售额" in context
    assert "SELECT SUM(total_amount) FROM orders" in context
    assert "结果列: value" in context


def test_store_keeps_sessions_isolated():
    store = make_store(max_turns=3)

    store.append_turn("session-a", make_state("A 问题"))
    store.append_turn("session-b", make_state("B 问题"))

    assert "A 问题" in store.get_context("session-a")
    assert "B 问题" not in store.get_context("session-a")


def test_store_keeps_only_recent_turns():
    store = make_store(max_turns=2)

    store.append_turn("session-1", make_state("第一轮"))
    store.append_turn("session-1", make_state("第二轮"))
    store.append_turn("session-1", make_state("第三轮"))

    context = store.get_context("session-1")

    assert "第一轮" not in context
    assert "第二轮" in context
    assert "第三轮" in context


def test_empty_or_missing_session_returns_empty_context():
    store = make_store()

    assert store.get_context(None) == ""
    assert store.get_context("") == ""
    assert store.get_context("missing") == ""


def test_store_does_not_save_unsafe_turn():
    store = make_store()
    state = make_state("读取本地文件", "SELECT * FROM read_csv_auto('/etc/passwd')")
    state["is_sql_safe"] = False
    state["execution_success"] = False

    store.append_turn("session-1", state)

    assert store.get_context("session-1") == ""


def test_store_does_not_save_intent_blocked_turn():
    store = make_store()
    state = make_state("删除所有订单")
    state["intent_is_safe"] = False

    store.append_turn("session-1", state)

    assert store.get_context("session-1") == ""


def test_store_treats_historical_state_without_intent_field_as_safe():
    store = make_store()
    state = make_state("统计订单数")

    store.append_turn("session-1", state)

    assert "统计订单数" in store.get_context("session-1")


def test_store_saves_failed_execution_as_minimal_record():
    store = make_store()
    state = make_state("查询不存在的表", "SELECT * FROM missing_table")
    state["execution_success"] = False
    state["execution_error"] = "Table missing_table does not exist"

    store.append_turn("session-1", state)

    context = store.get_context("session-1")
    assert "查询不存在的表" in context
    assert "执行失败" in context
    assert "Table missing_table does not exist" in context


def test_pending_clarification_roundtrip_uses_stable_candidate_id():
    store = make_store()
    clarification = {
        "clarification_id": "clarify_metric_001",
        "question": "您想分析什么指标？",
        "options": [
            {
                "candidate_id": "metric_sales_amount",
                "label": "销售额",
                "description": "分析销售额相关的数据",
            }
        ],
    }

    store.save_pending_clarification("session-1", "帮我分析一下", clarification)
    resolved = store.resolve_pending_clarification(
        "session-1",
        "clarify_metric_001",
        candidate_id="metric_sales_amount",
    )

    assert resolved is not None
    assert resolved["original_question"] == "帮我分析一下"
    assert resolved["candidate_id"] == "metric_sales_amount"
    assert resolved["resolved_question"] == "帮我分析一下。用户澄清：销售额（metric_sales_amount）"
    assert store.resolve_pending_clarification(
        "session-1",
        "clarify_metric_001",
        candidate_id="metric_sales_amount",
    ) is None


def test_pending_clarification_rejects_mismatched_candidate():
    store = make_store()
    store.save_pending_clarification(
        "session-1",
        "帮我分析一下",
        {
            "clarification_id": "clarify_metric_001",
            "question": "您想分析什么指标？",
            "options": [
                {
                    "candidate_id": "metric_sales_amount",
                    "label": "销售额",
                    "description": "分析销售额相关的数据",
                }
            ],
        },
    )

    assert store.resolve_pending_clarification(
        "session-1",
        "clarify_metric_001",
        candidate_id="metric_order_count",
    ) is None
