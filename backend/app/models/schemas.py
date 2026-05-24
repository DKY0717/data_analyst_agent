# Pydantic模型定义模块
# 定义请求和响应的数据模型

from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict
from datetime import datetime

# 请求模型
class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str = Field(..., min_length=1, max_length=1000, description="自然语言问题")

class SQLValidateRequest(BaseModel):
    """SQL验证请求模型"""
    sql: str = Field(..., min_length=1, description="需要验证的SQL语句")

class SQLExecuteRequest(BaseModel):
    """SQL执行请求模型"""
    sql: str = Field(..., min_length=1, description="需要执行的SQL语句")

# 响应模型
class SuccessResponse(BaseModel):
    """成功响应模型"""
    code: int = 200
    message: str = "success"
    data: Any

class ErrorResponse(BaseModel):
    """错误响应模型"""
    error_code: int
    error_type: str
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None

class QueryResponse(BaseModel):
    """查询响应模型"""
    question: str
    sql: str
    is_sql_safe: bool
    columns: List[str]
    rows: List[List[Any]]
    answer: str
    execution_time_ms: int
    retry_count: int
    optimization_suggestions: List[str] = []

class SchemaResponse(BaseModel):
    """Schema响应模型"""
    tables: Dict[str, List[Dict[str, str]]]

class SQLValidateResponse(BaseModel):
    """SQL验证响应模型"""
    is_safe: bool
    sanitized_sql: str
    reason: Optional[str] = None

class SQLExecuteResponse(BaseModel):
    """SQL执行响应模型"""
    success: bool
    columns: List[str] = []
    rows: List[List[Any]] = []
    execution_time_ms: int = 0
    error: Optional[str] = None
    error_type: Optional[str] = None

# Agent内部模型
class SQLGeneratorOutput(BaseModel):
    """SQL生成器输出模型"""
    sql: str
    tables: List[str]
    columns: List[str]
    explanation: str

class SQLRepairOutput(BaseModel):
    """SQL修复输出模型"""
    repaired_sql: str
    repair_reason: str

class AgentState(BaseModel):
    """Agent状态模型"""
    question: str
    schema_context: Optional[Dict[str, Any]] = None
    generated_sql: Optional[str] = None
    validated_sql: Optional[str] = None
    is_sql_safe: bool = False
    validation_error: Optional[str] = None
    execution_success: bool = False
    query_result: Optional[Dict[str, Any]] = None
    execution_error: Optional[str] = None
    retry_count: int = 0
    answer: Optional[str] = None
    optimization_suggestions: List[str] = []