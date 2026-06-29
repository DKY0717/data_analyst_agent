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
from .grounding import schema_grounder
from .clarification import clarification_engine
from .session_store import session_store
from .audit import audit_report_builder
from ..analysis_intent.models import AnalysisIntent
from ..analysis_intent.rule_parser import AnalysisIntentRuleParser
from ..analysis_intent.llm_parser import AnalysisIntentLLMParser
from ..analysis_intent.merger import AnalysisIntentMerger
from ..db.schema_loader import schema_loader
from ..security.intent_guard import intent_guard
from ..security.sql_guard import sql_guard
from ..security.data_permission import data_permission_guard
from ..db.query_runner import query_runner
from ..config import settings
from ..services.llm_observability import get_calls, start_trace
from ..services.tracing import trace_node, add_span_attributes, record_span_event
from ..utils.logger import logger


class AgentGraph:
    """LangGraph Agent 工作流，编排整个数据分析 pipeline"""

    def __init__(self):
        # 构建并编译工作流图
        self.rule_parser = AnalysisIntentRuleParser()
        self.llm_parser = AnalysisIntentLLMParser()
        self.intent_merger = AnalysisIntentMerger()
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """构建 LangGraph 状态图

        节点顺序:
        check_intent → parse_intent → ground_schema → assess_clarification
             ↓                                                ↓
          (不安全)                                      (需要澄清)
             ↓                                                ↓
            end                                             end
        assess_clarification → load_schema → generate_sql → validate_sql → authorize_sql → execute_sql
                                                                         ↓              ↓           ↓
                                                                      (不安全)       (无权限)     (执行失败)
                                                                         ↓              ↓           ↓
                                                                        end            end        repair_sql → validate_sql
        """
        workflow = StateGraph(AgentState)

        # 注册所有节点
        workflow.add_node("check_intent", self._check_intent)
        workflow.add_node("parse_intent", self._parse_intent)
        workflow.add_node("ground_schema", self._ground_schema)
        workflow.add_node("assess_clarification", self._assess_clarification)
        workflow.add_node("load_schema", self._load_schema)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("validate_sql", self._validate_sql)
        workflow.add_node("authorize_sql", self._authorize_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("repair_sql", self._repair_sql)
        workflow.add_node("optimize_sql", self._optimize_sql)
        workflow.add_node("generate_answer", self._generate_answer)

        # 设置入口节点
        workflow.set_entry_point("check_intent")

        # 固定边：线性流程
        workflow.add_edge("parse_intent", "ground_schema")
        workflow.add_edge("ground_schema", "assess_clarification")
        workflow.add_edge("load_schema", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")
        workflow.add_edge("generate_answer", END)

        # Intent Guard 是唯一入口，安全时进入意图解析，危险请求在读取 Schema 或调用任何外部依赖前终止。
        workflow.add_conditional_edges(
            "check_intent",
            self._should_load_schema,
            {
                "parse_intent": "parse_intent",
                "end": END,
            },
        )

        # 主动澄清是 SQL 生成前的暂停态，避免低置信问题继续消耗 Qwen 或访问数据库。
        workflow.add_conditional_edges(
            "assess_clarification",
            self._should_continue_after_intent,
            {
                "load_schema": "load_schema",
                "end": END,
            },
        )

        # 条件边：SQL 校验后先进入权限检查，Guard 拒绝的 SQL 直接终止
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_authorize_sql,
            {
                "authorize": "authorize_sql",  # SQL 安全，继续做数据权限检查
                "end": END                    # Guard 拒绝后立即终止，禁止修复代理改写危险意图
            }
        )

        # 条件边：权限通过后才能执行；权限阻断不进入 Repair，避免模型改写越权请求。
        workflow.add_conditional_edges(
            "authorize_sql",
            self._should_execute_authorized_sql,
            {
                "execute": "execute_sql",
                "end": END,
            },
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

    @trace_node("check_intent")
    async def _check_intent(self, state: AgentState) -> Dict[str, Any]:
        """在进入数据分析工作流前执行确定性意图安全检查。"""
        logger.info("节点: check_intent - 校验用户意图")
        await self._emit_progress(state, "校验意图安全性...", 10)
        try:
            result = intent_guard.validate(state["question"])
            is_safe = bool(result["is_safe"])
            reason = result.get("reason")
            answer = None if is_safe else f"请求已被安全策略阻断：{reason}"
            return {
                "status": "completed" if is_safe else "blocked",
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
                "status": "blocked",
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

    @trace_node("parse_intent")
    async def _parse_intent(self, state: AgentState) -> Dict[str, Any]:
        """分层意图解析：规则快速提取 + LLM 补充 + 合并冲突。"""
        logger.info("节点: parse_intent - 解析分析意图")
        await self._emit_progress(state, "解析分析意图...", 25)
        question = state["question"]

        # 规则层：快速、确定性，提取年份、Top-N、显式业务别名
        rule_intent = self.rule_parser.parse(question)

        # LLM 层：补充复杂、隐式和多意图场景（独立追踪，不污染主 llm_calls）
        llm_intent = None
        try:
            llm_intent = await self.llm_parser.parse(question)
        except Exception:
            logger.warning("LLM 意图解析失败，降级为纯规则结果")

        # 合并：规则优先，LLM 补充，冲突显式保留
        if llm_intent is not None:
            merged = self.intent_merger.merge(rule_intent, llm_intent)
        else:
            merged = rule_intent

        return {
            "status": "completed",
            "analysis_intent": merged.model_dump(),
            "audit_events": self._append_audit_event(
                state,
                "intent",
                "parse_intent",
                "success",
                "分析意图解析完成",
                details={
                    "metrics": [m.concept for m in merged.metrics],
                    "dimensions": [d.concept for d in merged.dimensions],
                    "confidence": merged.overall_confidence,
                },
            ),
        }

    @trace_node("ground_schema")
    def _ground_schema(self, state: AgentState) -> Dict[str, Any]:
        """将结构化业务意图映射到 Schema 候选和路由证据。"""
        logger.info("节点: ground_schema - 生成 Schema Grounding")
        self._emit_progress_sync(state, "生成 Schema Grounding...", 35)
        intent = self._analysis_intent_from_state(state)
        grounding_result = schema_grounder.ground(intent)

        # SQL Generator 仍读取 analysis_intent；这里把 Grounding 证据嵌回去，保持下游兼容。
        analysis_intent = {
            **intent.model_dump(),
            "grounding": grounding_result,
        }
        return {
            "grounding_result": grounding_result,
            "analysis_intent": analysis_intent,
            "audit_events": self._append_audit_event(
                state,
                "grounding",
                "ground_schema",
                "success",
                "Schema Grounding 完成",
                details={
                    "selected_tables": grounding_result.get("schema_route", {}).get(
                        "selected_tables", []
                    )
                },
            ),
        }

    @trace_node("assess_clarification")
    def _assess_clarification(self, state: AgentState) -> Dict[str, Any]:
        """根据意图缺口、冲突和会话恢复能力决定是否主动澄清。"""
        logger.info("节点: assess_clarification - 判断是否需要澄清")
        self._emit_progress_sync(state, "判断是否需要澄清...", 40)
        intent = self._analysis_intent_from_state(state)
        grounding_result = state.get("grounding_result") or {}
        clarification = clarification_engine.check(intent)
        if clarification and not self._should_request_clarification(state, intent):
            clarification = None
        clarification_payload = clarification.model_dump() if clarification else None

        analysis_intent = {
            **intent.model_dump(),
            "grounding": grounding_result,
            "clarification": clarification_payload,
        }
        if clarification_payload:
            return {
                "status": "clarification_required",
                "analysis_intent": analysis_intent,
                "clarification_request": clarification_payload,
                "answer": clarification_payload["question"],
                "audit_events": self._append_audit_event(
                    state,
                    "intent",
                    "clarify",
                    "blocked",
                    "分析意图不完整，已暂停并请求用户澄清",
                    details={
                        "clarification_id": clarification_payload["clarification_id"],
                        "reason": clarification_payload["reason"],
                    },
                ),
            }

        return {
            "status": "completed",
            "analysis_intent": analysis_intent,
            "clarification_request": None,
            "audit_events": self._append_audit_event(
                state,
                "intent",
                "assess_clarification",
                "success",
                "无需主动澄清，继续 SQL 生成流程",
            ),
        }

    @trace_node("load_schema")
    async def _load_schema(self, state: AgentState) -> Dict[str, Any]:
        """加载数据库 Schema，供后续 SQL 生成使用"""
        logger.info("节点: load_schema - 加载数据库 Schema")
        await self._emit_progress(state, "加载数据库 Schema...", 50)
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

    @trace_node("generate_sql")
    async def _generate_sql(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 将自然语言问题转换为 SQL"""
        logger.info("节点: generate_sql - 生成 SQL")
        await self._emit_progress(state, "生成 SQL 查询...", 65)
        start_trace(state.get("llm_calls") or [])
        output = await sql_generator.generate(
            state["question"],
            state["schema_context"],
            state.get("conversation_context") or "",
            state.get("analysis_intent"),
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

    @trace_node("validate_sql")
    async def _validate_sql(self, state: AgentState) -> Dict[str, Any]:
        """使用 SQL Guard 校验 SQL 安全性，自动注入 LIMIT"""
        logger.info("节点: validate_sql - 校验 SQL 安全性")
        await self._emit_progress(state, "校验 SQL 安全性...", 75)
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
            "status": "completed" if result["is_safe"] else "blocked",
            "validated_sql": result["sanitized_sql"],
            "is_sql_safe": result["is_safe"],
            "validation_error": result["reason"],
            "audit_events": audit_events,
        }

    @trace_node("authorize_sql")
    async def _authorize_sql(self, state: AgentState) -> Dict[str, Any]:
        """在执行前检查最终 SQL 的表/字段权限。"""
        logger.info("节点: authorize_sql - 校验数据权限")
        await self._emit_progress(state, "校验数据权限...", 80)
        result = data_permission_guard.authorize(
            state["validated_sql"],
            state.get("auth_user"),
            state.get("schema_context"),
        )
        return {
            "status": "completed" if result.is_allowed else "blocked",
            "validated_sql": result.authorized_sql if result.is_allowed else state["validated_sql"],
            "permission_allowed": result.is_allowed,
            "permission_error": None if result.is_allowed else result.reason,
            "answer": None if result.is_allowed else f"请求已被数据权限策略阻断：{result.reason}",
            "audit_events": self._extend_audit_events(state, result.audit_events),
        }

    @trace_node("execute_sql")
    async def _execute_sql(self, state: AgentState) -> Dict[str, Any]:
        """执行已通过校验的 SQL 查询"""
        logger.info("节点: execute_sql - 执行 SQL 查询")
        await self._emit_progress(state, "执行 SQL 查询...", 85)
        result = query_runner.execute(state["validated_sql"])
        status = "success" if result["success"] else "failed"
        return {
            "execution_success": result["success"],
            "query_result": result,
            "execution_error": result.get("error"),
            "execution_error_type": result.get("error_type"),
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

    @trace_node("repair_sql")
    async def _repair_sql(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 修复失败的 SQL，递增重试计数"""
        logger.info(f"节点: repair_sql - 修复 SQL (第 {state['retry_count'] + 1} 次)")
        await self._emit_progress(state, "修复 SQL 查询...", 80)

        # 修复代理只处理已通过 Guard 但执行失败的 SQL，禁止改写 Guard 拒绝的危险意图。
        error_message = state.get("execution_error") or ""
        error_type = state.get("execution_error_type") or ""

        start_trace(state.get("llm_calls") or [])
        output = await sql_repair_agent.repair(
            state["generated_sql"],
            error_message,
            state["schema_context"],
            error_type=error_type,
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

    @trace_node("optimize_sql")
    async def _optimize_sql(self, state: AgentState) -> Dict[str, Any]:
        """基于执行结果和 EXPLAIN 生成 SQL 优化建议"""
        logger.info("节点: optimize_sql - 生成 SQL 优化建议")
        await self._emit_progress(state, "生成优化建议...", 90)
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

    @trace_node("generate_answer")
    async def _generate_answer(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 将查询结果转换为自然语言解释"""
        logger.info("节点: generate_answer - 生成答案")
        await self._emit_progress(state, "生成分析结果...", 95)
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

    @staticmethod
    async def _emit_progress(state: AgentState, stage: str, progress: int) -> None:
        """调用进度回调（如果存在），用于 SSE 流式推送。"""
        cb = state.get("_on_progress")
        if cb:
            try:
                result = cb(stage, progress)
                if hasattr(result, '__await__'):
                    await result
            except Exception:
                pass

    @staticmethod
    def _emit_progress_sync(state: AgentState, stage: str, progress: int) -> None:
        """同步版本的进度回调，用于 LangGraph 在独立线程中运行的同步节点。"""
        cb = state.get("_on_progress")
        if cb:
            try:
                cb(stage, progress)
            except Exception:
                pass

    @staticmethod
    def _analysis_intent_from_state(state: AgentState) -> AnalysisIntent:
        """节点间用 dict 传递状态，进入业务逻辑前恢复 Pydantic 校验边界。"""
        return AnalysisIntent.model_validate(state.get("analysis_intent") or {})

    # ---- 条件判断函数 ----

    def _should_load_schema(self, state: AgentState) -> str:
        """意图安全时进入意图解析，否则立即终止。"""
        return "parse_intent" if state["intent_is_safe"] else "end"

    def _should_continue_after_intent(self, state: AgentState) -> str:
        """意图完整时继续加载 Schema；需要澄清时暂停在 SQL 生成前。"""
        return "end" if state.get("status") == "clarification_required" else "load_schema"

    def _should_request_clarification(
        self,
        state: AgentState,
        intent: Any,
    ) -> bool:
        """只拦截真正模糊的分析请求，避免普通查询和多轮追问被过度澄清。"""
        if not state.get("session_id"):
            return False

        if intent.conflicts:
            return True

        question = state.get("question", "")
        vague_markers = (
            "分析一下",
            "分析下",
            "帮我分析",
            "看一下数据",
            "看看数据",
            "数据情况",
            "整体情况",
        )
        has_metric_gap = "metric" in intent.missing_slots and not intent.metrics
        if has_metric_gap and any(marker in question for marker in vague_markers):
            return True

        # 多轮追问常常省略指标，例如“按地区拆一下”；有历史上下文时交给 SQL Generator 继承意图。
        if state.get("conversation_context"):
            return False

        return False

    def _should_authorize_sql(self, state: AgentState) -> str:
        """校验后决策：安全 SQL 继续授权，Guard 拒绝的 SQL 立即终止。"""
        if state["is_sql_safe"]:
            return "authorize"
        logger.warning(f"SQL 校验失败，已阻断执行: {state.get('validation_error')}")
        return "end"

    def _should_execute_authorized_sql(self, state: AgentState) -> str:
        """权限后决策：通过才执行，越权请求直接结束且不得进入 Repair。"""
        if state.get("permission_allowed"):
            return "execute"
        logger.warning(f"SQL 数据权限校验失败，已阻断执行: {state.get('permission_error')}")
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

    async def run(
        self,
        question: str,
        session_id: str | None = None,
        clarification_response: dict[str, Any] | None = None,
        auth_user: dict[str, Any] | None = None,
        on_progress: Any = None,
    ) -> AgentState:
        """运行完整的 Agent 工作流

        Args:
            question: 用户的自然语言问题
            session_id: 多轮分析会话 ID；为空时保持单轮查询行为

        Returns:
            最终的 AgentState，包含 answer 或错误信息
        """
        if clarification_response:
            resolved = session_store.resolve_pending_clarification(
                session_id,
                clarification_response["clarification_id"],
                candidate_id=clarification_response.get("candidate_id"),
                text=clarification_response.get("text"),
            )
            if resolved is None:
                return self._build_expired_clarification_state(question, session_id)
            question = resolved["resolved_question"]

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
            "status": "completed",
            "analysis_intent": None,
            "grounding_result": None,
            "clarification_request": None,
            "schema_context": None,
            "generated_sql": "",
            "validated_sql": "",
            "is_sql_safe": False,
            "validation_error": None,
            "execution_success": False,
            "query_result": None,
            "execution_error": None,
            "execution_error_type": None,
            "retry_count": 0,
            "answer": None,
            "optimization_suggestions": [],
            "audit_events": [],
            "audit_report": None,
            "llm_calls": [],
            "auth_user": auth_user,
            "permission_allowed": True,
            "permission_error": None,
        }

        # 进度追踪：将 on_progress 回调注入到 state 中，供各节点调用
        if on_progress:
            initial_state["_on_progress"] = on_progress

        # 不在日志中记录原始问题，避免危险请求或凭据值进入日志。
        logger.info("开始处理用户问题")
        final_state = await self.graph.ainvoke(initial_state)
        logger.info(f"处理完成，重试次数: {final_state['retry_count']}")

        final_state["audit_report"] = audit_report_builder.build_report(
            final_state,
            final_state.get("audit_events", []),
        )

        if final_state.get("status") == "clarification_required":
            session_store.save_pending_clarification(
                session_id,
                final_state["question"],
                final_state.get("clarification_request") or {},
            )
            return final_state

        # 权限阻断的 SQL 不能进入多轮上下文，避免下一轮 Prompt 继承越权字段或表名。
        if final_state.get("permission_allowed") is False:
            return final_state

        # 图完成后再写回本轮摘要；失败轮也保留问题和 SQL，方便下一轮提示用户换问法或继续修复。
        session_store.append_turn(session_id, final_state)

        return final_state

    def _build_expired_clarification_state(
        self,
        question: str,
        session_id: str | None,
    ) -> AgentState:
        """澄清恢复失败时返回稳定状态，不继续调用下游依赖。"""
        event = audit_report_builder.make_event(
            "intent",
            "resolve_clarification",
            "blocked",
            "澄清请求已过期或候选无效，请重新提问",
            rule_id="clarification_not_found",
        )
        state: AgentState = {
            "question": question,
            "intent_is_safe": True,
            "intent_rule_id": None,
            "intent_category": None,
            "intent_error": None,
            "session_id": session_id,
            "conversation_context": "",
            "status": "clarification_expired",
            "analysis_intent": None,
            "grounding_result": None,
            "clarification_request": None,
            "schema_context": None,
            "generated_sql": "",
            "validated_sql": "",
            "is_sql_safe": False,
            "validation_error": "澄清请求已过期或候选无效",
            "execution_success": False,
            "query_result": None,
            "execution_error": None,
            "execution_error_type": None,
            "retry_count": 0,
            "answer": "澄清请求已过期或候选无效，请重新提问。",
            "optimization_suggestions": [],
            "audit_events": [event],
            "audit_report": None,
            "llm_calls": [],
            "auth_user": None,
            "permission_allowed": True,
            "permission_error": None,
        }
        state["audit_report"] = audit_report_builder.build_report(state, [event])
        return state


# 延迟初始化：避免模块 import 时触发数据库连接和级联初始化
_agent_graph_instance: AgentGraph | None = None


def get_agent_graph() -> AgentGraph:
    """获取全局 AgentGraph 单例（首次调用时才初始化）"""
    global _agent_graph_instance
    if _agent_graph_instance is None:
        _agent_graph_instance = AgentGraph()
    return _agent_graph_instance
