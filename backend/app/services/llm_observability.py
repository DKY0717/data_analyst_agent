# LLM 调用可观测性模块
# 使用 ContextVar 隔离并发异步请求，统一汇总 Token、耗时、尝试次数和可选成本。

from contextvars import ContextVar
from copy import deepcopy
from typing import Any, Dict, List, Optional


_llm_calls: ContextVar[List[Dict[str, Any]]] = ContextVar("llm_calls", default=[])


def start_trace() -> None:
    """为当前异步请求创建全新的调用轨迹，避免复用全局客户端时串数据。"""
    _llm_calls.set([])


def record_call(call: Dict[str, Any]) -> None:
    """追加一次调用指标；复制旧列表以保持 ContextVar 上下文隔离。"""
    calls = get_calls()
    calls.append(deepcopy(call))
    _llm_calls.set(calls)


def get_calls() -> List[Dict[str, Any]]:
    """返回当前请求调用轨迹的深拷贝，防止调用方原地修改共享指标。"""
    return deepcopy(_llm_calls.get())


def calculate_estimated_cost(
    input_tokens: int,
    output_tokens: int,
    input_price: Optional[float],
    output_price: Optional[float],
) -> Optional[float]:
    """按每百万 Token 单价估算成本；价格不完整时不伪造金额。"""
    if input_price is None or output_price is None:
        return None
    return (
        input_tokens / 1_000_000 * input_price
        + output_tokens / 1_000_000 * output_price
    )


def summarize(calls: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """将调用明细汇总为请求级指标，供审计报告和离线评测复用。"""
    call_list = deepcopy(calls) if calls is not None else get_calls()
    costs = [call.get("estimated_cost") for call in call_list]
    cost_available = bool(call_list) and all(cost is not None for cost in costs)

    return {
        "call_count": len(call_list),
        "input_tokens": sum(call.get("input_tokens", 0) for call in call_list),
        "output_tokens": sum(call.get("output_tokens", 0) for call in call_list),
        "total_tokens": sum(call.get("total_tokens", 0) for call in call_list),
        "total_latency_ms": sum(call.get("latency_ms", 0) for call in call_list),
        "total_attempt_count": sum(call.get("attempt_count", 0) for call in call_list),
        "estimated_cost": sum(costs) if cost_available else None,
        "cost_available": cost_available,
        "calls": call_list,
    }
