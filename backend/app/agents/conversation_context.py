# 多轮分析上下文构建器
# 将上一轮 Agent 结果压缩成短文本，供 SQL Generator 理解用户追问。

from typing import Any, Dict, List


class ConversationContextBuilder:
    """把历史分析结果转成 LLM prompt 可读的轻量摘要。"""

    def __init__(self, max_turns: int = 3, answer_max_chars: int = 120):
        self.max_turns = max_turns
        self.answer_max_chars = answer_max_chars

    def extract_turn(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """从 Agent final state 中提取可安全复用的上下文字段。"""
        query_result = final_state.get("query_result") or {}

        # 只保留列名、行数和答案摘要，不保存 rows，避免历史结果过大污染 prompt。
        return {
            "question": final_state.get("question") or "",
            "sql": final_state.get("validated_sql") or final_state.get("generated_sql") or "",
            "columns": query_result.get("columns", []),
            "row_count": query_result.get("row_count", len(query_result.get("rows", []))),
            "answer_summary": self._truncate(final_state.get("answer") or ""),
            "optimization_suggestions": final_state.get("optimization_suggestions", []),
            "success": True,
        }

    def extract_failed_turn(self, final_state: Dict[str, Any]) -> Dict[str, Any]:
        """提取失败轮的精简上下文，只保留问题和错误信息。"""
        return {
            "question": final_state.get("question") or "",
            "sql": final_state.get("validated_sql") or final_state.get("generated_sql") or "",
            "error": self._truncate(final_state.get("execution_error") or "未知错误"),
            "success": False,
        }

    def build_context(self, turns: List[Dict[str, Any]]) -> str:
        """把最近几轮历史拼成 prompt 上下文。"""
        if not turns:
            return ""

        recent_turns = turns[-self.max_turns:]
        lines = [
            "上一轮分析上下文:",
            "用户可能会基于这些结果继续追问；如果追问省略了指标、维度或过滤条件，请优先继承最近一轮分析意图。",
        ]

        for index, turn in enumerate(recent_turns, start=1):
            if turn.get("success") is False:
                lines.extend([
                    f"第 {index} 轮:",
                    f"- 问题: {turn.get('question', '')}",
                    f"- SQL: {turn.get('sql', '')}",
                    f"- 状态: 执行失败 - {turn.get('error', '未知错误')}",
                ])
            else:
                columns = ", ".join(turn.get("columns", [])) or "无"
                suggestions = "；".join(turn.get("optimization_suggestions", [])) or "无"
                lines.extend(
                    [
                        f"第 {index} 轮:",
                        f"- 问题: {turn.get('question', '')}",
                        f"- SQL: {turn.get('sql', '')}",
                        f"- 结果列: {columns}",
                        f"- 结果行数: {turn.get('row_count', 0)}",
                        f"- 答案摘要: {turn.get('answer_summary', '') or '无'}",
                        f"- 优化建议: {suggestions}",
                    ]
                )

        return "\n".join(lines)

    def _truncate(self, text: str) -> str:
        """答案摘要只截断到固定长度，保持 prompt 可控。"""
        if len(text) <= self.answer_max_chars:
            return text
        return text[:self.answer_max_chars] + "..."


conversation_context_builder = ConversationContextBuilder()
