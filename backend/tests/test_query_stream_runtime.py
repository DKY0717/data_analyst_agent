"""SSE 心跳、断连与 Agent task 清理回归测试。"""

import asyncio

import pytest

from app.api.query import _cancel_pipeline_task, _wait_for_stream_event


class DisconnectableRequest:
    def __init__(self, disconnected: bool):
        self.disconnected = disconnected

    async def is_disconnected(self):
        return self.disconnected


@pytest.mark.asyncio
async def test_stream_wait_emits_heartbeat_while_pipeline_is_running():
    queue = asyncio.Queue()
    task = asyncio.create_task(asyncio.sleep(60))
    try:
        event = await _wait_for_stream_event(
            queue,
            task,
            DisconnectableRequest(False),
            heartbeat_seconds=0.001,
        )
    finally:
        await _cancel_pipeline_task(task)

    assert event == {"type": "heartbeat"}


@pytest.mark.asyncio
async def test_stream_wait_detects_client_disconnect():
    task = asyncio.create_task(asyncio.sleep(60))
    try:
        event = await _wait_for_stream_event(
            asyncio.Queue(),
            task,
            DisconnectableRequest(True),
            heartbeat_seconds=0.001,
        )
    finally:
        await _cancel_pipeline_task(task)

    assert event == {"type": "disconnect"}


@pytest.mark.asyncio
async def test_cancel_pipeline_task_waits_for_cancellation_cleanup():
    cancelled = asyncio.Event()

    async def pipeline():
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    task = asyncio.create_task(pipeline())
    await asyncio.sleep(0)

    await _cancel_pipeline_task(task)

    assert task.cancelled() is True
    assert cancelled.is_set() is True
