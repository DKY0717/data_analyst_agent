"""Agent 进度通知旁路，统一同步/异步回调与脱敏错误处理。"""

import asyncio
import inspect
from collections.abc import Awaitable, Mapping
from typing import Any

from ..utils.logger import logger


def _log_callback_failure(stage: str, exc: Exception) -> None:
    """只记录内部阶段和异常类型，避免回调异常携带问题、SQL 或 Secret。"""
    logger.warning(
        "进度回调失败: stage=%s error_type=%s",
        stage,
        type(exc).__name__,
    )


async def _await_safely(awaitable: Awaitable[Any], stage: str) -> None:
    """等待异步回调并在旁路内部消化失败，不改变 Agent 主流程结果。"""
    try:
        await awaitable
    except Exception as exc:
        _log_callback_failure(stage, exc)


async def notify_progress(
    state: Mapping[str, Any],
    stage: str,
    progress: int,
) -> None:
    """从异步节点发送进度；普通函数和 awaitable 回调均受支持。"""
    callback = state.get("_on_progress")
    if callback is None:
        return

    try:
        result = callback(stage, progress)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        _log_callback_failure(stage, exc)


def notify_progress_sync(
    state: Mapping[str, Any],
    stage: str,
    progress: int,
) -> None:
    """从同步节点发送进度，并安全桥接回调返回的 awaitable。"""
    callback = state.get("_on_progress")
    if callback is None:
        return

    try:
        result = callback(stage, progress)
        if not inspect.isawaitable(result):
            return

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            # LangGraph 通常在线程中运行同步节点，此处创建短生命周期事件循环等待回调完成。
            asyncio.run(_await_safely(result, stage))
        else:
            # 若同步入口恰好位于活动事件循环中，调度任务避免嵌套 run_until_complete。
            running_loop.create_task(_await_safely(result, stage))
    except Exception as exc:
        _log_callback_failure(stage, exc)

