# Pydantic模型定义模块
# 定义请求和响应的数据模型

from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional, List, Dict

# 请求模型
class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str = Field(..., min_length=1, max_length=1000, description="自然语言问题")
    session_id: Optional[str] = Field(None, max_length=128, description="多轮分析会话ID")
    clarification_id: Optional[str] = Field(None, max_length=128, description="主动澄清请求ID")
    clarification_candidate_id: Optional[str] = Field(None, max_length=128, description="用户选择的澄清候选ID")
    clarification_text: Optional[str] = Field(None, max_length=300, description="用户自由文本澄清回答")

class SQLValidateRequest(BaseModel):
    """SQL验证请求模型"""
    sql: str = Field(..., min_length=1, description="需要验证的SQL语句")

class SQLExecuteRequest(BaseModel):
    """SQL执行请求模型"""
    sql: str = Field(..., min_length=1, description="需要执行的SQL语句")

# 响应模型
class SuccessResponse(BaseModel):
    """成功响应模型"""
    code: int = 200  # 响应状态码
    message: str = "success"  # 响应消息
    data: Any  # 响应数据

class ErrorResponse(BaseModel):
    """错误响应模型"""
    error_code: int  # 错误码
    error_type: str  # 错误类型
    message: str  # 错误消息
    details: Optional[Any] = None  # 错误详情
    request_id: Optional[str] = None  # 请求ID

class AuditEvent(BaseModel):
    """单条安全审计事件"""
    stage: str  # 事件阶段，如 generation/guard/execution
    action: str  # 具体动作，如 validate_sql
    status: str  # success/blocked/failed
    message: str  # 面向用户的事件说明
    rule_id: Optional[str] = None  # 命中的安全规则ID
    details: Dict[str, Any] = Field(default_factory=dict)  # 事件附加信息


class LLMCallMetrics(BaseModel):
    """单次 LLM 逻辑调用指标，不包含 prompt、密钥和原始响应"""
    stage: str = "unknown"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    attempt_count: int = 0
    estimated_cost: Optional[float] = None
    success: bool = False
    error_type: Optional[str] = None


class LLMObservability(BaseModel):
    """一次 Agent 请求内全部 LLM 调用的汇总"""
    call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: int = 0
    total_attempt_count: int = 0
    estimated_cost: Optional[float] = None
    cost_available: bool = False
    calls: List[LLMCallMetrics] = Field(default_factory=list)


class PermissionObservability(BaseModel):
    """一次请求内数据权限检查的稳定摘要，不暴露完整策略。"""
    permission_checked: bool = False
    allowed: Optional[bool] = None
    blocked_rule: Optional[str] = None
    referenced_tables: List[str] = Field(default_factory=list)
    referenced_columns: List[str] = Field(default_factory=list)
    row_filters_applied: List[Dict[str, str]] = Field(default_factory=list)
    authorized_sql_changed: bool = False


class AuditReport(BaseModel):
    """一次查询的安全审计报告"""
    question: str = ""  # 用户问题
    user_id: Optional[str] = None  # 当前认证用户 ID；未启用认证时为空
    auth_method: Optional[str] = None  # jwt / api_key / disabled 等认证方式
    roles: List[str] = Field(default_factory=list)  # 当前用户角色摘要，不暴露完整权限策略
    final_sql: str = ""  # 最终校验或执行 SQL
    is_sql_safe: bool = False  # 最终 SQL 是否安全
    execution_success: bool = False  # 是否执行成功
    retry_count: int = 0  # 修复重试次数
    limit_injected: bool = False  # 是否发生自动 LIMIT 注入
    blocked_rules: List[str] = Field(default_factory=list)  # 被命中的阻断规则
    llm_observability: LLMObservability = Field(default_factory=LLMObservability)  # LLM 调用汇总
    permission_observability: PermissionObservability = Field(default_factory=PermissionObservability)  # 权限检查摘要
    events: List[AuditEvent] = Field(default_factory=list)  # 审计事件明细

class QueryResponse(BaseModel):
    """查询响应模型"""
    model_config = ConfigDict(extra="forbid")

    question: str  # 用户问题
    session_id: Optional[str] = None  # 多轮分析会话ID
    status: str = "completed"  # completed / blocked / clarification_required / clarification_expired
    intent_is_safe: bool = True  # Intent Guard 是否允许进入后续工作流
    intent_rule_id: Optional[str] = None  # Intent Guard 命中的规则 ID
    intent_category: Optional[str] = None  # Intent Guard 命中的风险类别
    sql: str  # 生成的SQL语句
    is_sql_safe: bool  # SQL是否安全
    columns: List[str]  # 查询结果列名
    rows: List[List[Any]]  # 查询结果数据行
    answer: str  # 自然语言回答
    execution_time_ms: int  # 执行耗时（毫秒）
    retry_count: int  # 重试次数
    optimization_suggestions: List[str] = Field(default_factory=list)  # 优化建议列表
    analysis_intent: Optional[Dict[str, Any]] = None  # 分层意图解析结果
    clarification: Optional[Dict[str, Any]] = None  # 主动澄清请求，前端按 candidate_id 恢复任务
    audit_report: Optional[AuditReport] = None  # 安全审计报告

class SchemaResponse(BaseModel):
    """Schema响应模型"""
    tables: Dict[str, Dict[str, Any]]  # 表结构信息，key 为表名，value 为表详情

class SQLValidateResponse(BaseModel):
    """SQL验证响应模型"""
    is_safe: bool  # SQL是否安全
    sanitized_sql: str  # 清理后的SQL语句
    reason: Optional[str] = None  # 不安全原因

class SQLExecuteResponse(BaseModel):
    """SQL执行响应模型"""
    success: bool  # 是否执行成功
    columns: List[str] = Field(default_factory=list)  # 查询结果列名
    rows: List[List[Any]] = Field(default_factory=list)  # 查询结果数据行
    execution_time_ms: int = 0  # 执行耗时（毫秒）
    error: Optional[str] = None  # 错误信息
    error_type: Optional[str] = None  # 错误类型

# Agent内部模型
class SQLGeneratorOutput(BaseModel):
    """SQL生成器输出模型"""
    sql: str  # 生成的SQL语句
    tables: List[str]  # 使用的表名列表
    columns: List[str]  # 使用的字段名列表
    explanation: str  # SQL查询逻辑说明

class SQLRepairOutput(BaseModel):
    """SQL修复输出模型"""
    repaired_sql: str  # 修复后的SQL语句
    repair_reason: str  # 修复原因说明


