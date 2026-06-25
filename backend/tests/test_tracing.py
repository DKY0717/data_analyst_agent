# OpenTelemetry 追踪测试

from app.services.tracing import get_tracer, init_tracing, add_span_attributes, record_span_event


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
