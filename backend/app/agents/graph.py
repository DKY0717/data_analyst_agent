# LangGraph Agent 工作流模块
# 将 Schema 加载、SQL 生成、SQL 校验、SQL 执行、SQL 修复、答案生成串联为完整 pipeline
# 使用 LangGraph 的 StateGraph 定义节点和条件边，实现自动重试和错误修复

from typing import Dict, Any
from langgraph.graph import StateGraph, END

from .state import AgentState
from .sql_generator import sql_generator
from .sql_repair import sql_repair_agent
from .answer_generator import answer_generator
from .sql_optimizer import sql_optimizer
from .session_store import session_store
from .audit import audit_report_builder
from ..db.schema_loader import schema_loader
from ..security.intent_guard import intent_guard
from ..security.sql_guard import sql_guard
from ..db.query_runner import query_runner
from ..config import settings
from ..services.llm_observability import get_calls, start_trace
from ..utils.logger import logger


class AgentGraph:
    """LangGraph Agent 工作流，编排整个数据分析 pipeline"""

    def __init__(self):
        # 构建并编译工作流图
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """构建 LangGraph 状态图

        节点顺序:
        check_intent → load_schema → generate_sql → validate_sql → execute_sql → generate_answer
             ↓                                           ↓           ↓
          (不安全)                                    (不安全)     (执行失败)
             ↓                                           ↓           ↓
            end                                         end        repair_sql → validate_sql (循环)
        """
        workflow = StateGraph(AgentState)

        # 注册所有节点
        workflow.add_node("check_intent", self._check_intent)
        workflow.add_node("load_schema", self._load_schema)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("validate_sql", self._validate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("repair_sql", self._repair_sql)
        workflow.add_node("optimize_sql", self._optimize_sql)
        workflow.add_node("generate_answer", self._generate_answer)

        # 设置入口节点
        workflow.set_entry_point("check_intent")

        # 固定边：线性流程
        workflow.add_edge("load_schema", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")
        workflow.add_edge("generate_answer", END)

        # Intent Guard 是唯一入口，危险请求在读取 Schema 或调用任何外部依赖前终止。
        workflow.add_conditional_edges(
            "check_intent",
            self._should_load_schema,
            {
                "load_schema": "load_schema",
                "end": END,
            },
        )

        # 条件边：SQL 校验后决定执行还是修复还是终止
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_execute,
            {
                "execute": "execute_sql",     # SQL 安全，执行
                "end": END                    # Guard 拒绝后立即终止，禁止修复代理改写危险意图
            }
        )

        # 条件边：SQL 执行后决定生成答案还是修复还是终止
        workflow.add_conditional_edges(
            "execute_sql",
            self._should_continue,
            {
                "answer": "optimize_sql",      # 执行成功，先生成优化建议
                "repair": "repair_sql",       # 执行失败且可重试，修复
                "end": END                    # 执行失败且重试耗尽，终止
            }
        )

        # 修复后必须再次经过校验（不能直接执行，防止修复出不安全的 SQL）
        workflow.add_edge("repair_sql", "validate_sql")
        workflow.add_edge("optimize_sql", "generate_answer")

        return workflow.compile()

    # ---- 节点实现 ----

    async def _check_intent(self, state: AgentState) -> Dict[str, Any]:
        """在进入数据分析工作流前执行确定性意图安全检查。"""
        logger.info("节点: check_intent - 校验用户意图")
        try:
            result = intent_guard.validate(state["question"])
            is_safe = bool(result["is_safe"])
            reason = result.get("reason")
            answer = None if is_safe else f"请求已被安全策略阻断：{reason}"
            return {
                "intent_is_safe": is_safe,
                "intent_rule_id": result.get("rule_id"),
                "intent_category": result.get("category"),
                "intent_error": reason,
                "answer": answer,
                "audit_events": self._append_audit_event(
                    state,
                    "intent",
                    "check_intent",
                    "success" if is_safe else "blocked",
                    "用户意图通过安全检查" if is_safe else reason,
                    rule_id=result.get("rule_id"),
                    details={"category": result.get("category")} if result.get("category") else None,
                ),
            }
        except Exception:
            # 调用或结果解析异常时均 fail-closed，日志不携带问题、异常消息或潜在敏感值。
            logger.warning("Intent Guard 安全检查异常，已阻断请求")
            reason = "安全检查暂时不可用，请稍后重试"
            return {
                "intent_is_safe": False,
                "intent_rule_id": "block_intent_guard_error",
                "intent_category": "guard_error",
                "intent_error": reason,
                "answer": reason,
                "audit_events": self._append_audit_event(
                    state,
                    "intent",
                    "check_intent",
                    "blocked",
                    reason,
                    rule_id="block_intent_guard_error",
                ),
            }

    async def _load_schema(self, state: AgentState) -> Dict[str, Any]:
        """加载数据库 Schema，供后续 SQL 生成使用"""
        logger.info("节点: load_schema - 加载数据库 Schema")
        schema = schema_loader.get_full_schema()
        return {
            "schema_context": schema,
            "audit_events": self._append_audit_event(
                state,
                "schema",
                "load_schema",
                "success",
                "数据库 Schema 加载完成",
                details={"table_count": len(schema.get("tables", {}))},
            ),
        }

    async def _generate_sql(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 将自然语言问题转换为 SQL"""
        logger.info("节点: generate_sql - 生成 SQL")
        start_trace(state.get("llm_calls") or [])
        output = await sql_generator.generate(
            state["question"],
            state["schema_context"],
            state.get("conversation_context") or ""
        )
        return {
            "generated_sql": output.sql,
            "llm_calls": get_calls(),
            "audit_events": self._append_audit_event(
                state,
                "generation",
                "generate_sql",
                "success",
                "LLM 已生成 SQL",
                details={"sql": output.sql, "tables": output.tables},
            ),
        }

    async def _validate_sql(self, state: AgentState) -> Dict[str, Any]:
        """使用 SQL Guard 校验 SQL 安全性，自动注入 LIMIT"""
        logger.info("节点: validate_sql - 校验 SQL 安全性")
        result = sql_guard.validate(state["generated_sql"])
        audit_events = self._extend_audit_events(state, result.get("audit_events", []))
        if not result.get("audit_events"):
            audit_events = audit_events + [
                audit_report_builder.make_event(
                    "guard",
                    "validate_sql",
                    "success" if result["is_safe"] else "blocked",
                    result.get("reason") or "SQL 通过安全校验",
                    rule_id=result.get("blocked_rule"),
                    details={"limit_injected": result.get("limit_injected", False)},
                )
            ]
        return {
            "validated_sql": result["sanitized_sql"],
            "is_sql_safe": result["is_safe"],
            "validation_error": result["reason"],
            "audit_events": audit_events,
        }

    async def _execute_sql(self, state: AgentState) -> Dict[str, Any]:
        """执行已通过校验的 SQL 查询"""
        logger.info("节点: execute_sql - 执行 SQL 查询")
        result = query_runner.execute(state["validated_sql"])
        status = "success" if result["success"] else "failed"
        return {
            "execution_success": result["success"],
            "query_result": result,
            "execution_error": result.get("error"),
            "audit_events": self._append_audit_event(
                state,
                "execution",
                "execute_sql",
                status,
                "SQL 执行成功" if result["success"] else result.get("error", "SQL 执行失败"),
                details={
                    "execution_time_ms": result.get("execution_time_ms", 0),
                    "row_count": result.get("row_count", len(result.get("rows", []))),
                    "error_type": result.get("error_type"),
                },
            ),
        }

    async def _repair_sql(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 修复失败的 SQL，递增重试计数"""
        logger.info(f"节点: repair_sql - 修复 SQL (第 {state['retry_count'] + 1} 次)")

        # 修复代理只处理已通过 Guard 但执行失败的 SQL，禁止改写 Guard 拒绝的危险意图。
        error_message = state.get("execution_error") or ""

        start_trace(state.get("llm_calls") or [])
        output = await sql_repair_agent.repair(
            state["generated_sql"],
            error_message,
            state["schema_context"]
        )

        return {
            "generated_sql": output.repaired_sql,
            "retry_count": state["retry_count"] + 1,
            "llm_calls": get_calls(),
            "audit_events": self._append_audit_event(
                state,
                "repair",
                "repair_sql",
                "success",
                output.repair_reason,
                details={
                    "retry_count": state["retry_count"] + 1,
                    "repaired_sql": output.repaired_sql,
                },
            ),
        }

    async def _optimize_sql(self, state: AgentState) -> Dict[str, Any]:
        """基于执行结果和 EXPLAIN 生成 SQL 优化建议"""
        logger.info("节点: optimize_sql - 生成 SQL 优化建议")
        suggestions = sql_optimizer.optimize(
            state["validated_sql"],
            state["query_result"]
        )
        return {
            "optimization_suggestions": suggestions,
            "audit_events": self._append_audit_event(
                state,
                "optimization",
                "optimize_sql",
                "success",
                "SQL 优化建议生成完成",
                details={"suggestion_count": len(suggestions)},
            ),
        }

    async def _generate_answer(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 将查询结果转换为自然语言解释"""
        logger.info("节点: generate_answer - 生成答案")
        start_trace(state.get("llm_calls") or [])
        answer = await answer_generator.generate(
            state["question"],
            state["validated_sql"],
            state["query_result"]
        )
        return {
            "answer": answer,
            "llm_calls": get_calls(),
            "audit_events": self._append_audit_event(
                state,
                "answer",
                "generate_answer",
                "success",
                "自然语言答案生成完成",
            ),
        }

    def _append_audit_event(
        self,
        state: AgentState,
        stage: str,
        action: str,
        status: str,
        message: str,
        rule_id: str | None = None,
        details: Dict[str, Any] | None = None,
    ) -> list[Dict[str, Any]]:
        """节点通过返回新列表追加审计事件，避免直接原地修改 LangGraph state。"""
        return self._extend_audit_events(
            state,
            [audit_report_builder.make_event(stage, action, status, message, rule_id, details)],
        )

    def _extend_audit_events(
        self,
        state: AgentState,
        new_events: list[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        """合并已有审计事件和节点新事件。"""
        return list(state.get("audit_events") or []) + new_events

    # ---- 条件判断函数 ----

    def _should_load_schema(self, state: AgentState) -> str:
        """意图安全时进入 Schema 加载，否则立即终止。"""
        return "load_schema" if state["intent_is_safe"] else "end"

    def _should_execute(self, state: AgentState) -> str:
        """校验后决策：安全 SQL 执行，Guard 拒绝的 SQL 立即终止。"""
        if state["is_sql_safe"]:
            return "execute"
        logger.warning(f"SQL 校验失败，已阻断执行: {state.get('validation_error')}")
        return "end"

    def _should_continue(self, state: AgentState) -> str:
        """执行后决策：成功→生成答案，失败且可重试→修复，否则→终止"""
        if state["execution_success"]:
            return "answer"
        if state["retry_count"] < settings.SQL_MAX_RETRIES:
            return "repair"
        # 重试耗尽，返回终止
        logger.warning(f"SQL 执行失败且重试耗尽: {state.get('execution_error')}")
        return "end"

    async def run(self, question: str, session_id: str | None = None) -> AgentState:
        """运行完整的 Agent 工作流

        Args:
            question: 用户的自然语言问题
            session_id: 多轮分析会话 ID；为空时保持单轮查询行为

        Returns:
            最终的 AgentState，包含 answer 或错误信息
        """
        # 在图执行前读取历史摘要，作为显式 state 传入后续节点，避免节点直接访问外部会话存储。
        conversation_context = session_store.get_context(session_id)
        start_trace()

        # 初始化状态，所有字段设为默认值
        initial_state: AgentState = {
            "question": question,
            "intent_is_safe": False,
            "intent_rule_id": None,
            "intent_category": None,
            "intent_error": None,
            "session_id": session_id,
            "conversation_context": conversation_context,
            "schema_context": None,
            "generated_sql": "",
            "validated_sql": "",
            "is_sql_safe": False,
            "validation_error": None,
            "execution_success": False,
            "query_result": None,
            "execution_error": None,
            "retry_count": 0,
            "answer": None,
            "optimization_suggestions": [],
            "audit_events": [],
            "audit_report": None,
            "llm_calls": [],
        }

        # 不在日志中记录原始问题，避免危险请求或凭据值进入日志。
        logger.info("开始处理用户问题")
        final_state = await self.graph.ainvoke(initial_state)
        logger.info(f"处理完成，重试次数: {final_state['retry_count']}")

        final_state["audit_report"] = audit_report_builder.build_report(
            final_state,
            final_state.get("audit_events", []),
        )

        # 图完成后再写回本轮摘要；失败轮也保留问题和 SQL，方便下一轮提示用户换问法或继续修复。
        session_store.append_turn(session_id, final_state)

        return final_state


# 全局 Agent 工作流实例
agent_graph = AgentGraph()
