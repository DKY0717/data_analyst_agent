# OpenTelemetry 追踪测试

from app.services.tracing import (
    _record_result_attributes,
    add_span_attributes,
    get_tracer,
    init_tracing,
    record_span_event,
)


class CapturingSpan:
    """最小 span 替身，用于验证不会输出 SQL 原文。"""

    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


def test_init_tracing():
    # 不应抛出异常
    init_tracing()


def test_get_tracer():
    tracer = get_tracer()
    assert tracer is not None


def test_create_span():
    tracer = get_tracer()
    with tracer.start_as_current_span("test_span") as span:
        assert span.is_recording()
        span.set_attribute("test.key", "test_value")


def test_add_span_attributes():
    tracer = get_tracer()
    with tracer.start_as_current_span("test_span"):
        # 不应抛出异常
        add_span_attributes({"key1": "value1", "key2": 42})


def test_record_span_event():
    tracer = get_tracer()
    with tracer.start_as_current_span("test_span"):
        record_span_event("test_event", {"event_key": "event_value"})


def test_result_attributes_store_sql_fingerprint_without_query_text_or_literals():
    span = CapturingSpan()
    same_shape_span = CapturingSpan()
    secret = "private-customer-13800138000"

    _record_result_attributes(
        span,
        {
            "generated_sql": f"SELECT order_id FROM orders WHERE customer_name = '{secret}'",
            "validated_sql": (
                f"SELECT order_id FROM orders WHERE customer_name = '{secret}' LIMIT 1000"
            ),
            "is_sql_safe": True,
        },
    )
    _record_result_attributes(
        same_shape_span,
        {
            "validated_sql": (
                "SELECT order_id FROM orders "
                "WHERE customer_name = 'another-private-customer' LIMIT 50"
            )
        },
    )

    assert "sql.generated" not in span.attributes
    assert "sql.validated" not in span.attributes
    assert span.attributes["sql.statement_type"] == "SELECT"
    assert span.attributes["sql.tables"] == "orders"
    assert len(span.attributes["sql.hash"]) == 16
    assert same_shape_span.attributes["sql.hash"] == span.attributes["sql.hash"]
    assert secret not in repr(span.attributes)
