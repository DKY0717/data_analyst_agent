# 安全审计报告构建器
# 统一生成审计事件和最终报告，让 Guard、AgentGraph、API 共用同一种结构。

from typing import Any, Dict, List, Optional

from ..services.llm_observability import summarize


class AuditReportBuilder:
    """创建审计事件，并从最终 AgentState 汇总审计报告。"""

    def make_event(
        self,
        stage: str,
        action: str,
        status: str,
        message: str,
        rule_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成稳定结构的审计事件，便于 API 和前端直接展示。"""
        return {
            "stage": stage,
            "action": action,
            "status": status,
            "message": message,
            "rule_id": rule_id,
            "details": details or {},
        }

    def build_report(self, final_state: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从最终状态和事件列表汇总审计报告。"""
        # LIMIT 注入可能发生在任意一次 Guard 校验中，报告层只关心是否发生过。
        limit_injected = any(event.get("details", {}).get("limit_injected") for event in events)
        # 同一规则可能在多次修复重试中重复命中，报告只保留首次出现，事件明细仍保留完整过程。
        blocked_rules = list(
            dict.fromkeys(
                event["rule_id"]
                for event in events
                if event.get("status") == "blocked" and event.get("rule_id")
            )
        )

        return {
            "question": final_state.get("question", ""),
            "final_sql": final_state.get("validated_sql") or final_state.get("generated_sql") or "",
            "is_sql_safe": bool(final_state.get("is_sql_safe")),
            "execution_success": bool(final_state.get("execution_success")),
            "retry_count": final_state.get("retry_count", 0),
            "limit_injected": limit_injected,
            "blocked_rules": blocked_rules,
            "llm_observability": summarize(final_state.get("llm_calls") or []),
            "events": events,
        }


audit_report_builder = AuditReportBuilder()
