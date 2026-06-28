# OpenTelemetry 分布式追踪模块
# 提供请求级别的全链路追踪，覆盖 Agent 工作流每个节点

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import Status, StatusCode

from ..config import settings
from ..utils.logger import logger


# 全局 tracer 实例
_tracer: Optional[trace.Tracer] = None


def init_tracing(service_name: str = "data-analyst-agent") -> None:
    """初始化 OpenTelemetry 追踪

    支持三种导出方式（通过 OTEL_EXPORTER 环境变量控制）：
    - console: 输出到控制台（开发调试用）
    - otlp: 导出到 OTLP 收集器（Jaeger、Zipkin 等）
    - none: 禁用追踪
    """
    global _tracer

    exporter_type = os.getenv("OTEL_EXPORTER", "console").lower()

    resource = Resource.create({
        SERVICE_NAME: service_name,
        "deployment.environment": "production" if not settings.DEBUG else "development",
    })

    provider = TracerProvider(resource=resource)

    if exporter_type == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter()
            logger.info("OpenTelemetry OTLP 导出器已启用")
        except Exception as e:
            logger.warning(f"OTLP 导出器初始化失败，回退到控制台: {e}")
            exporter = ConsoleSpanExporter()
    elif exporter_type == "none":
        # 只关闭导出，不关闭 SDK tracer；测试和本地调试仍可创建 recording span。
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
        logger.info("OpenTelemetry 追踪已禁用")
        return
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)

    logger.info(f"OpenTelemetry 追踪已初始化 (导出方式: {exporter_type})")


def get_tracer() -> trace.Tracer:
    """获取全局 tracer"""
    global _tracer
    if _tracer is None:
        init_tracing()
    return _tracer


def trace_node(node_name: str):
    """装饰器：为 Agent 节点创建追踪 span（支持同步和异步函数）

    用法:
        @trace_node("generate_sql")
        async def _generate_sql(self, state):
            ...

        @trace_node("ground_schema")
        def _ground_schema(self, state):
            ...
    """
    import asyncio

    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                with tracer.start_as_current_span(
                    node_name,
                    attributes={"agent.node": node_name},
                ) as span:
                    try:
                        result = await func(*args, **kwargs)
                        _record_result_attributes(span, result)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                with tracer.start_as_current_span(
                    node_name,
                    attributes={"agent.node": node_name},
                ) as span:
                    try:
                        result = func(*args, **kwargs)
                        _record_result_attributes(span, result)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            return sync_wrapper

    return decorator


def _record_result_attributes(span, result):
    """从节点返回值中提取关键属性记录到 span"""
    if isinstance(result, dict):
        if "generated_sql" in result:
            span.set_attribute("sql.generated", result["generated_sql"][:200])
        if "validated_sql" in result:
            span.set_attribute("sql.validated", result["validated_sql"][:200])
        if "is_sql_safe" in result:
            span.set_attribute("sql.safe", result["is_sql_safe"])
        if "execution_success" in result:
            span.set_attribute("execution.success", result["execution_success"])
        if "retry_count" in result:
            span.set_attribute("retry.count", result["retry_count"])
        if "error" in result.get("query_result", {}):
            span.set_attribute("error.type", result["query_result"].get("error_type", ""))


def add_span_attributes(attributes: dict) -> None:
    """在当前活跃 span 上添加属性"""
    span = trace.get_current_span()
    if span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def record_span_event(name: str, attributes: dict = None) -> None:
    """在当前活跃 span 上记录事件"""
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(name, attributes=attributes or {})
