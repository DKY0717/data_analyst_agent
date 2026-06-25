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
        self._pending_clarifications: Dict[str, Dict[str, Any]] = {}

    def append_turn(self, session_id: Optional[str], final_state: Dict[str, Any]) -> None:
        """保存一轮结果；没有 session_id 时保持单轮行为，不写历史。"""
        if not session_id:
            return

        # 历史状态可能没有 intent 字段，只有显式阻断时才拒绝保存，保持旧会话兼容。
        if final_state.get("intent_is_safe", True) is False:
            return

        # Guard 拒绝的危险意图不进入上下文，避免污染后续 prompt。
        if not final_state.get("is_sql_safe"):
            return

        # 执行失败的轮次保存精简摘要（问题 + 错误），让下一轮 LLM 知道发生了什么。
        if not final_state.get("execution_success"):
            self._sessions[session_id].append(
                self.context_builder.extract_failed_turn(final_state)
            )
            return

        # 只保存 builder 提取出的摘要，避免把完整 AgentState 或大结果集长期留在内存里。
        self._sessions[session_id].append(self.context_builder.extract_turn(final_state))

    def get_context(self, session_id: Optional[str]) -> str:
        """返回该 session 最近几轮的 prompt 上下文。"""
        if not session_id:
            return ""

        turns = list(self._sessions.get(session_id, []))
        return self.context_builder.build_context(turns)

    def save_pending_clarification(
        self,
        session_id: Optional[str],
        question: str,
        clarification: Dict[str, Any],
    ) -> None:
        """保存等待用户选择的澄清请求；没有 session_id 时无法安全恢复任务。"""
        if not session_id:
            return

        # pending 澄清不进入历史上下文，只作为下一次 candidate_id 恢复的冻结状态。
        self._pending_clarifications[session_id] = {
            "question": question,
            "clarification": clarification,
        }

    def resolve_pending_clarification(
        self,
        session_id: Optional[str],
        clarification_id: str,
        *,
        candidate_id: Optional[str] = None,
        text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """按稳定候选 ID 或自由文本恢复原问题，恢复成功后消费 pending 请求。"""
        if not session_id:
            return None

        pending = self._pending_clarifications.get(session_id)
        if not pending:
            return None

        clarification = pending.get("clarification", {})
        if clarification.get("clarification_id") != clarification_id:
            return None

        option = self._match_clarification_option(
            clarification.get("options", []),
            candidate_id,
            text,
        )
        if option is None:
            return None

        self._pending_clarifications.pop(session_id, None)
        original_question = pending["question"]
        selected_label = option["label"]
        selected_id = option["candidate_id"]
        return {
            "original_question": original_question,
            "candidate_id": selected_id,
            "label": selected_label,
            "resolved_question": f"{original_question}。用户澄清：{selected_label}（{selected_id}）",
        }

    @staticmethod
    def _match_clarification_option(
        options: list[Dict[str, Any]],
        candidate_id: Optional[str],
        text: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """自由文本也必须归一化到已有候选，防止恢复时引入新歧义。"""
        normalized_text = (text or "").strip().casefold()
        for option in options:
            if candidate_id and option.get("candidate_id") == candidate_id:
                return option
            labels = [
                option.get("label", ""),
                option.get("description", ""),
                option.get("candidate_id", ""),
            ]
            if normalized_text and any(
                normalized_text == str(label).strip().casefold()
                for label in labels
            ):
                return option
        return None

    def clear(self, session_id: Optional[str] = None) -> None:
        """测试或调试时清理历史；生产接口暂不暴露该能力。"""
        if session_id:
            self._sessions.pop(session_id, None)
            self._pending_clarifications.pop(session_id, None)
            return
        self._sessions.clear()
        self._pending_clarifications.clear()


session_store = SessionStore()
