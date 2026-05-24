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

class QueryResponse(BaseModel):
    """查询响应模型"""
    question: str  # 用户问题
    sql: str  # 生成的SQL语句
    is_sql_safe: bool  # SQL是否安全
    columns: List[str]  # 查询结果列名
    rows: List[List[Any]]  # 查询结果数据行
    answer: str  # 自然语言回答
    execution_time_ms: int  # 执行耗时（毫秒）
    retry_count: int  # 重试次数
    optimization_suggestions: List[str] = []  # 优化建议列表

class SchemaResponse(BaseModel):
    """Schema响应模型"""
    tables: Dict[str, List[Dict[str, str]]]  # 表结构信息

class SQLValidateResponse(BaseModel):
    """SQL验证响应模型"""
    is_safe: bool  # SQL是否安全
    sanitized_sql: str  # 清理后的SQL语句
    reason: Optional[str] = None  # 不安全原因

class SQLExecuteResponse(BaseModel):
    """SQL执行响应模型"""
    success: bool  # 是否执行成功
    columns: List[str] = []  # 查询结果列名
    rows: List[List[Any]] = []  # 查询结果数据行
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

class AgentState(BaseModel):
    """Agent状态模型"""
    question: str  # 用户原始问题
    schema_context: Optional[Dict[str, Any]] = None  # 数据库Schema上下文
    generated_sql: Optional[str] = None  # 生成的SQL语句
    validated_sql: Optional[str] = None  # 验证后的SQL语句
    is_sql_safe: bool = False  # SQL是否安全
    validation_error: Optional[str] = None  # 验证错误信息
    execution_success: bool = False  # 是否执行成功
    query_result: Optional[Dict[str, Any]] = None  # 查询结果
    execution_error: Optional[str] = None  # 执行错误信息
    retry_count: int = 0  # 重试次数
    answer: Optional[str] = None  # 自然语言回答
    optimization_suggestions: List[str] = []  # 优化建议列表