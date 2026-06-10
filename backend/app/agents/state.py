# Agent 状态定义模块
# 定义 LangGraph 工作流中所有节点共享的状态结构
# 使用 TypedDict 而非 Pydantic BaseModel，因为 LangGraph StateGraph 需要 TypedDict

from typing import TypedDict, Any, Optional, Dict, List


class AgentState(TypedDict):
    """Agent 工作流共享状态

    所有节点（load_schema、generate_sql、validate_sql 等）都通过这个状态字典通信。
    每个节点读取需要的字段，写入产出的字段。

    字段说明:
        question: 用户的原始自然语言问题
        schema_context: 数据库 Schema 信息，由 load_schema 节点填充
        generated_sql: LLM 生成的 SQL 语句
        validated_sql: 经过 SQL Guard 校验和清理后的 SQL（含自动 LIMIT）
        is_sql_safe: SQL Guard 校验结果
        validation_error: SQL Guard 校验失败的原因
        execution_success: SQL 执行是否成功
        query_result: SQL 执行结果，包含 columns、rows、execution_time_ms
        execution_error: SQL 执行失败的错误信息
        retry_count: SQL 修复重试次数，最多 3 次
        answer: LLM 生成的自然语言回答
        optimization_suggestions: SQL 优化建议（预留字段）
        session_id: 多轮分析会话 ID，不传则按单轮查询处理
        conversation_context: 由历史会话生成的追问上下文摘要
        audit_events: 安全审计事件列表
        audit_report: 最终安全审计报告
        llm_calls: 当前请求内的 LLM 调用指标列表
    """
    question: str
    session_id: Optional[str]
    conversation_context: Optional[str]
    schema_context: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    validated_sql: Optional[str]
    is_sql_safe: bool
    validation_error: Optional[str]
    execution_success: bool
    query_result: Optional[Dict[str, Any]]
    execution_error: Optional[str]
    retry_count: int
    answer: Optional[str]
    optimization_suggestions: List[str]
    audit_events: List[Dict[str, Any]]
    audit_report: Optional[Dict[str, Any]]
    llm_calls: List[Dict[str, Any]]
