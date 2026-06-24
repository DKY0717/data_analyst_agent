# 内存会话存储测试
# SessionStore 是多轮分析的入口，测试重点是隔离 session、限制历史长度和生成上下文。

from app.agents.session_store import SessionStore


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


def test_append_turn_and_get_context():
    store = SessionStore(max_turns=3)

    store.append_turn("session-1", make_state("统计销售额", "SELECT SUM(total_amount) FROM orders"))

    context = store.get_context("session-1")

    assert "统计销售额" in context
    assert "SELECT SUM(total_amount) FROM orders" in context
    assert "结果列: value" in context


def test_store_keeps_sessions_isolated():
    store = SessionStore(max_turns=3)

    store.append_turn("session-a", make_state("A 问题"))
    store.append_turn("session-b", make_state("B 问题"))

    assert "A 问题" in store.get_context("session-a")
    assert "B 问题" not in store.get_context("session-a")


def test_store_keeps_only_recent_turns():
    store = SessionStore(max_turns=2)

    store.append_turn("session-1", make_state("第一轮"))
    store.append_turn("session-1", make_state("第二轮"))
    store.append_turn("session-1", make_state("第三轮"))

    context = store.get_context("session-1")

    assert "第一轮" not in context
    assert "第二轮" in context
    assert "第三轮" in context


def test_empty_or_missing_session_returns_empty_context():
    store = SessionStore()

    assert store.get_context(None) == ""
    assert store.get_context("") == ""
    assert store.get_context("missing") == ""


def test_store_does_not_save_unsafe_turn():
    store = SessionStore()
    state = make_state("读取本地文件", "SELECT * FROM read_csv_auto('/etc/passwd')")
    state["is_sql_safe"] = False
    state["execution_success"] = False

    store.append_turn("session-1", state)

    assert store.get_context("session-1") == ""


def test_store_does_not_save_intent_blocked_turn():
    store = SessionStore()
    state = make_state("删除所有订单")
    state["intent_is_safe"] = False

    store.append_turn("session-1", state)

    assert store.get_context("session-1") == ""


def test_store_treats_historical_state_without_intent_field_as_safe():
    store = SessionStore()
    state = make_state("统计订单数")

    store.append_turn("session-1", state)

    assert "统计订单数" in store.get_context("session-1")


def test_store_saves_failed_execution_as_minimal_record():
    store = SessionStore()
    state = make_state("查询不存在的表", "SELECT * FROM missing_table")
    state["execution_success"] = False
    state["execution_error"] = "Table missing_table does not exist"

    store.append_turn("session-1", state)

    context = store.get_context("session-1")
    assert "查询不存在的表" in context
    assert "执行失败" in context
    assert "Table missing_table does not exist" in context
