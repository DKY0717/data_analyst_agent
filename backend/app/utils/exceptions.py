# 自定义异常模块
# 定义项目中所有自定义异常类

class AppException(Exception):
    """应用程序基础异常类"""
    pass

class DatabaseError(AppException):
    """数据库操作异常"""
    pass

class SQLGuardError(AppException):
    """SQL安全校验异常"""
    pass

class SQLExecutionError(AppException):
    """SQL执行异常"""
    pass

class SQLRepairError(AppException):
    """SQL修复异常"""
    pass

class LLMError(AppException):
    """LLM API调用异常"""
    pass

class LLMTimeoutError(LLMError):
    """LLM API超时异常"""
    pass

class LLMResponseError(LLMError):
    """LLM API响应异常"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider_code: str | None = None,
        provider_type: str | None = None,
    ):
        super().__init__(message)
        # 只保存调用边界清洗后的短元数据；供应商原始 message 不进入异常对象。
        self.status_code = status_code
        self.provider_code = provider_code
        self.provider_type = provider_type

class SchemaLoadError(AppException):
    """Schema加载异常"""
    pass
