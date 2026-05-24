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
    pass

class SchemaLoadError(AppException):
    """Schema加载异常"""
    pass