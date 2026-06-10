# 审计报告构建器测试
# 审计报告用于向用户和面试官展示“系统为什么认为这条 SQL 安全或不安全”。

from app.agents.audit import AuditReportBuilder


def test_make_event_uses_stable_shape():
    builder = AuditReportBuilder()

    event = builder.make_event(
        stage="guard",
        action="validate_sql",
        status="blocked",
        message="禁止访问系统表",
        rule_id="block_system_schema",
        details={"schema": "information_schema"},
    )

    assert event["stage"] == "guard"
    assert event["action"] == "validate_sql"
    assert event["status"] == "blocked"
    assert event["message"] == "禁止访问系统表"
    assert event["rule_id"] == "block_system_schema"
    assert event["details"] == {"schema": "information_schema"}


def test_build_report_summarizes_events_and_final_state():
    builder = AuditReportBuilder()
    events = [
        builder.make_event("generation", "generate_sql", "success", "SQL 生成成功"),
        builder.make_event(
            "guard",
            "validate_sql",
            "success",
            "SQL 通过校验",
            details={"limit_injected": True},
        ),
        builder.make_event("execution", "execute_sql", "success", "SQL 执行成功"),
    ]
    final_state = {
        "question": "统计订单数",
        "generated_sql": "SELECT COUNT(*) FROM orders",
        "validated_sql": "SELECT COUNT(*) FROM orders LIMIT 1000",
        "is_sql_safe": True,
        "execution_success": True,
        "retry_count": 0,
    }

    report = builder.build_report(final_state, events)

    assert report["question"] == "统计订单数"
    assert report["final_sql"] == "SELECT COUNT(*) FROM orders LIMIT 1000"
    assert report["is_sql_safe"] is True
    assert report["execution_success"] is True
    assert report["retry_count"] == 0
    assert report["limit_injected"] is True
    assert report["blocked_rules"] == []
    assert report["events"] == events


def test_build_report_collects_blocked_rules():
    builder = AuditReportBuilder()
    events = [
        builder.make_event(
            "guard",
            "validate_sql",
            "blocked",
            "危险函数被拦截",
            rule_id="block_dangerous_function",
        ),
    ]

    report = builder.build_report({"is_sql_safe": False, "execution_success": False, "retry_count": 0}, events)

    assert report["blocked_rules"] == ["block_dangerous_function"]
    assert report["limit_injected"] is False


def test_build_report_collects_intent_blocked_rule():
    builder = AuditReportBuilder()
    events = [
        builder.make_event(
            "intent",
            "check_intent",
            "blocked",
            "请求包含明确的数据修改或删除意图",
            rule_id="block_destructive_intent",
        ),
    ]

    report = builder.build_report(
        {
            "intent_is_safe": False,
            "intent_rule_id": "block_destructive_intent",
            "generated_sql": "",
            "validated_sql": "",
            "is_sql_safe": False,
            "execution_success": False,
            "retry_count": 0,
            "llm_calls": [],
        },
        events,
    )

    assert report["final_sql"] == ""
    assert report["blocked_rules"] == ["block_destructive_intent"]
    assert report["events"][0]["stage"] == "intent"


def test_build_report_deduplicates_blocked_rules_across_retries():
    builder = AuditReportBuilder()
    events = [
        builder.make_event(
            "guard",
            "validate_sql",
            "blocked",
            "危险函数被拦截",
            rule_id="block_dangerous_function",
        ),
        builder.make_event(
            "guard",
            "validate_sql",
            "blocked",
            "修复后仍包含危险函数",
            rule_id="block_dangerous_function",
        ),
    ]

    report = builder.build_report({"is_sql_safe": False}, events)

    assert report["blocked_rules"] == ["block_dangerous_function"]


def test_build_report_summarizes_llm_calls():
    builder = AuditReportBuilder()
    llm_calls = [
        {
            "stage": "generate_sql",
            "model": "qwen-plus",
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "latency_ms": 500,
            "attempt_count": 1,
            "estimated_cost": 0.001,
            "success": True,
            "error_type": None,
        },
        {
            "stage": "generate_answer",
            "model": "qwen-plus",
            "input_tokens": 80,
            "output_tokens": 30,
            "total_tokens": 110,
            "latency_ms": 300,
            "attempt_count": 1,
            "estimated_cost": 0.002,
            "success": True,
            "error_type": None,
        },
    ]

    report = builder.build_report({"llm_calls": llm_calls}, [])

    assert report["llm_observability"]["call_count"] == 2
    assert report["llm_observability"]["total_tokens"] == 230
    assert report["llm_observability"]["total_latency_ms"] == 800
    assert report["llm_observability"]["estimated_cost"] == 0.003
