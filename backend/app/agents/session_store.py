# 内存版多轮会话存储
# v0.3 先用轻量内存实现证明多轮分析能力，后续可替换为 Redis 或数据库持久化。

from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional

from .conversation_context import conversation_context_builder, ConversationContextBuilder


class SessionStore:
    """按 session_id 保存最近几轮 Agent 分析摘要。"""

    def __init__(
        self,
        max_turns: int = 3,
        context_builder: ConversationContextBuilder = conversation_context_builder,
    ):
        self.max_turns = max_turns
        self.context_builder = context_builder
        self._sessions: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=max_turns))

    def append_turn(self, session_id: Optional[str], final_state: Dict[str, Any]) -> None:
        """保存一轮结果；没有 session_id 时保持单轮行为，不写历史。"""
        if not session_id:
            return

        # 历史状态可能没有 intent 字段，只有显式阻断时才拒绝保存，保持旧会话兼容。
        if final_state.get("intent_is_safe", True) is False:
            return

        # 只让已通过 Guard 且执行成功的分析进入后续上下文，避免失败 SQL 或危险意图污染下一轮 prompt。
        if not final_state.get("is_sql_safe") or not final_state.get("execution_success"):
            return

        # 只保存 builder 提取出的摘要，避免把完整 AgentState 或大结果集长期留在内存里。
        self._sessions[session_id].append(self.context_builder.extract_turn(final_state))

    def get_context(self, session_id: Optional[str]) -> str:
        """返回该 session 最近几轮的 prompt 上下文。"""
        if not session_id:
            return ""

        turns = list(self._sessions.get(session_id, []))
        return self.context_builder.build_context(turns)

    def clear(self, session_id: Optional[str] = None) -> None:
        """测试或调试时清理历史；生产接口暂不暴露该能力。"""
        if session_id:
            self._sessions.pop(session_id, None)
            return
        self._sessions.clear()


session_store = SessionStore()
