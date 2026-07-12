"""Agent 进度通知旁路的同步、异步与隐私边界测试。"""

import asyncio
import logging

import pytest

from app.agents.progress_notifier import notify_progress, notify_progress_sync


@pytest.mark.asyncio
async def test_async_notifier_accepts_sync_and_async_callbacks():
    received = []

    def sync_callback(stage, progress):
        received.append(("sync", stage, progress))

    async def async_callback(stage, progress):
        received.append(("async", stage, progress))

    await notify_progress({"_on_progress": sync_callback}, "解析意图", 25)
    await notify_progress({"_on_progress": async_callback}, "生成 SQL", 65)

    assert received == [
        ("sync", "解析意图", 25),
        ("async", "生成 SQL", 65),
    ]


@pytest.mark.asyncio
async def test_async_notifier_ignores_missing_callback():
    await notify_progress({}, "解析意图", 25)


def test_sync_notifier_accepts_sync_and_awaitable_callbacks():
    received = []

    def sync_callback(stage, progress):
        received.append(("sync", stage, progress))

    async def async_callback(stage, progress):
        received.append(("async", stage, progress))

    notify_progress_sync({"_on_progress": sync_callback}, "加载 Schema", 50)
    notify_progress_sync({"_on_progress": async_callback}, "生成 Grounding", 35)

    assert received == [
        ("sync", "加载 Schema", 50),
        ("async", "生成 Grounding", 35),
    ]


@pytest.mark.asyncio
async def test_sync_notifier_schedules_awaitable_when_loop_is_running():
    completed = asyncio.Event()

    async def async_callback(_stage, _progress):
        completed.set()

    notify_progress_sync({"_on_progress": async_callback}, "生成 Grounding", 35)
    await asyncio.wait_for(completed.wait(), timeout=1)


@pytest.mark.asyncio
async def test_async_notifier_logs_only_stage_and_error_type(caplog):
    sensitive_message = "QWEN_API_KEY=private-progress-secret"

    async def broken_callback(_stage, _progress):
        raise RuntimeError(sensitive_message)

    with caplog.at_level(logging.WARNING, logger="data_analyst_agent"):
        await notify_progress({"_on_progress": broken_callback}, "生成答案", 95)

    assert "生成答案" in caplog.text
    assert "RuntimeError" in caplog.text
    assert sensitive_message not in caplog.text
    assert "private-progress-secret" not in caplog.text


def test_sync_notifier_logs_awaitable_failure_without_leaking_message(caplog):
    sensitive_message = "customer_name=private-customer"

    async def broken_callback(_stage, _progress):
        raise ValueError(sensitive_message)

    with caplog.at_level(logging.WARNING, logger="data_analyst_agent"):
        notify_progress_sync({"_on_progress": broken_callback}, "生成 Grounding", 35)

    assert "生成 Grounding" in caplog.text
    assert "ValueError" in caplog.text
    assert sensitive_message not in caplog.text
    assert "private-customer" not in caplog.text
