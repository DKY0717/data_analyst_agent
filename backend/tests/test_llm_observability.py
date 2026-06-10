# LLM 调用可观测性测试
# 验证调用轨迹在异步任务间隔离，并正确汇总 Token、耗时、尝试次数和可选成本。

import asyncio

import pytest

from app.services.llm_observability import (
    calculate_estimated_cost,
    get_calls,
    record_call,
    start_trace,
    summarize,
)


def make_call(stage: str, tokens: int, cost: float | None = 0.003):
    return {
        "stage": stage,
        "model": "qwen-plus",
        "input_tokens": tokens - 200,
        "output_tokens": 200,
        "total_tokens": tokens,
        "latency_ms": 800,
        "attempt_count": 1,
        "estimated_cost": cost,
        "success": True,
        "error_type": None,
    }


def test_summarize_calls_calculates_tokens_latency_attempts_and_cost():
    start_trace()
    record_call(make_call("generate_sql", 1200, 0.003))
    record_call(make_call("generate_answer", 800, 0.002))

    summary = summarize()

    assert summary["call_count"] == 2
    assert summary["input_tokens"] == 1600
    assert summary["output_tokens"] == 400
    assert summary["total_tokens"] == 2000
    assert summary["total_latency_ms"] == 1600
    assert summary["total_attempt_count"] == 2
    assert summary["estimated_cost"] == pytest.approx(0.005)
    assert summary["cost_available"] is True
    assert len(summary["calls"]) == 2


def test_summary_cost_is_none_when_any_call_cost_is_unavailable():
    start_trace()
    record_call(make_call("generate_sql", 1200, 0.003))
    record_call(make_call("generate_answer", 800, None))

    summary = summarize()

    assert summary["estimated_cost"] is None
    assert summary["cost_available"] is False


def test_calculate_estimated_cost_uses_per_million_token_prices():
    cost = calculate_estimated_cost(
        input_tokens=1_000_000,
        output_tokens=500_000,
        input_price=2.0,
        output_price=6.0,
    )

    assert cost == pytest.approx(5.0)


def test_calculate_estimated_cost_is_none_when_prices_are_missing():
    assert calculate_estimated_cost(1000, 200, None, None) is None
    assert calculate_estimated_cost(1000, 200, 2.0, None) is None


def test_get_calls_returns_copy():
    start_trace()
    record_call(make_call("generate_sql", 1200))

    calls = get_calls()
    calls[0]["stage"] = "changed"
    calls.append(make_call("repair_sql", 300))

    assert get_calls()[0]["stage"] == "generate_sql"
    assert len(get_calls()) == 1


@pytest.mark.asyncio
async def test_context_traces_are_isolated_between_async_tasks():
    async def collect(stage: str, tokens: int):
        start_trace()
        record_call(make_call(stage, tokens))
        await asyncio.sleep(0)
        return get_calls()

    first, second = await asyncio.gather(
        collect("generate_sql", 1200),
        collect("repair_sql", 500),
    )

    assert [call["stage"] for call in first] == ["generate_sql"]
    assert [call["stage"] for call in second] == ["repair_sql"]
    assert first[0]["total_tokens"] == 1200
    assert second[0]["total_tokens"] == 500
