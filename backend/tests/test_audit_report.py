# 审计报告构建器测试
# 审计报告用于向用户和面试官展示“系统为什么认为这条 SQL 安全或不安全”。

from app.agents.audit import AuditReportBuilder
from app.models.schemas import AuditReport


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


def test_build_report_includes_auth_identity_summary():
    builder = AuditReportBuilder()
    final_state = {
        "auth_user": {
            "user_id": "user:demo",
            "auth_method": "jwt",
            "roles": ["analyst"],
        }
    }

    report = builder.build_report(final_state, [])

    assert report["user_id"] == "user:demo"
    assert report["auth_method"] == "jwt"
    assert report["roles"] == ["analyst"]
    assert "ROLE_POLICIES" not in repr(report)


def test_build_report_omits_auth_fields_when_absent():
    builder = AuditReportBuilder()

    report = builder.build_report({}, [])
    parsed = AuditReport(**report)

    assert parsed.user_id is None
    assert parsed.auth_method is None
    assert parsed.roles == []


def test_permission_blocked_rule_is_summarized_once():
    builder = AuditReportBuilder()
    events = [
        builder.make_event(
            "authorization",
            "authorize_sql",
            "blocked",
            "当前角色无权访问字段: customers.customer_name",
            rule_id="block_unauthorized_column",
        ),
        builder.make_event(
            "authorization",
            "authorize_sql",
            "blocked",
            "当前角色无权访问字段: customers.customer_name",
            rule_id="block_unauthorized_column",
        ),
    ]

    report = builder.build_report({"is_sql_safe": True}, events)

    assert report["blocked_rules"] == ["block_unauthorized_column"]


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


def test_build_report_includes_empty_permission_observability_by_default():
    builder = AuditReportBuilder()

    report = builder.build_report({}, [])
    parsed = AuditReport(**report)

    assert parsed.permission_observability.permission_checked is False
    assert parsed.permission_observability.allowed is None
    assert parsed.permission_observability.blocked_rule is None
    assert parsed.permission_observability.referenced_tables == []
    assert parsed.permission_observability.referenced_columns == []
    assert parsed.permission_observability.row_filters_applied == []
    assert parsed.permission_observability.authorized_sql_changed is False


def test_build_report_summarizes_allowed_row_filter_permission_event():
    builder = AuditReportBuilder()
    events = [
        builder.make_event(
            "authorization",
            "authorize_sql",
            "success",
            "SQL 通过数据权限检查",
            rule_id="row_filter_applied",
            details={
                "tables": ["orders"],
                "columns_checked": ["orders.total_amount"],
                "row_filters_applied": [
                    {"table": "orders", "rule_id": "row_filter_region_scope"}
                ],
                "authorized_sql_changed": True,
            },
        )
    ]

    report = builder.build_report({"is_sql_safe": True}, events)

    permission = report["permission_observability"]
    assert permission["permission_checked"] is True
    assert permission["allowed"] is True
    assert permission["blocked_rule"] is None
    assert permission["referenced_tables"] == ["orders"]
    assert permission["referenced_columns"] == ["orders.total_amount"]
    assert permission["row_filters_applied"] == [
        {"table": "orders", "rule_id": "row_filter_region_scope"}
    ]
    assert permission["authorized_sql_changed"] is True
    assert "SELECT customer_id FROM customers" not in repr(permission)


def test_build_report_summarizes_blocked_permission_event():
    builder = AuditReportBuilder()
    events = [
        builder.make_event(
            "authorization",
            "authorize_sql",
            "blocked",
            "当前角色无权访问字段: customers.customer_name",
            rule_id="block_unauthorized_column",
            details={
                "tables": ["customers"],
                "columns_checked": ["customers.customer_name"],
            },
        )
    ]

    report = builder.build_report({"is_sql_safe": True}, events)

    permission = report["permission_observability"]
    assert permission["permission_checked"] is True
    assert permission["allowed"] is False
    assert permission["blocked_rule"] == "block_unauthorized_column"
    assert permission["referenced_tables"] == ["customers"]
    assert permission["referenced_columns"] == ["customers.customer_name"]
    assert permission["row_filters_applied"] == []
    assert permission["authorized_sql_changed"] is False
