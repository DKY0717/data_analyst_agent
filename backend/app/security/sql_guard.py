# SQL安全校验模块
# 使用SQLGlot进行SQL AST解析，验证SQL语句的安全性

import sqlglot
from typing import Dict, Any, Optional

from ..utils.logger import logger
from ..utils.exceptions import SQLGuardError
from ..config import settings

class SQLGuard:
    """SQL安全校验器"""

    # 允许的语句类型
    ALLOWED_STATEMENTS = {"SELECT", "WITH"}

    # 禁止的语句类型
    BLOCKED_STATEMENTS = {
        "DROP", "DELETE", "UPDATE", "INSERT",
        "ALTER", "TRUNCATE", "CREATE", "MERGE",
        "CALL", "EXECUTE", "GRANT", "REVOKE"
    }

    def __init__(self, max_rows: int = None):
        """
        初始化SQL Guard

        Args:
            max_rows: 最大返回行数，默认使用配置中的SQL_MAX_ROWS
        """
        self.max_rows = max_rows or settings.SQL_MAX_ROWS

    def validate(self, sql: str) -> Dict[str, Any]:
        """
        验证SQL安全性

        Args:
            sql: SQL语句

        Returns:
            包含is_safe、sanitized_sql、reason的字典
        """
        try:
            # 解析SQL
            parsed = sqlglot.parse_one(sql, dialect="duckdb")

            # 检查语句类型
            statement_type = parsed.key.upper()

            if statement_type not in self.ALLOWED_STATEMENTS:
                if statement_type in self.BLOCKED_STATEMENTS:
                    return {
                        "is_safe": False,
                        "sanitized_sql": sql,
                        "reason": f"禁止的语句类型: {statement_type}"
                    }
                else:
                    return {
                        "is_safe": False,
                        "sanitized_sql": sql,
                        "reason": f"未知的语句类型: {statement_type}"
                    }

            # 检查是否包含多个语句
            statements = sqlglot.parse(sql, dialect="duckdb")
            if len(statements) > 1:
                return {
                    "is_safe": False,
                    "sanitized_sql": sql,
                    "reason": "不允许执行多个语句"
                }

            # 清理SQL
            sanitized_sql = self._sanitize_sql(parsed)

            return {
                "is_safe": True,
                "sanitized_sql": sanitized_sql,
                "reason": None
            }

        except Exception as e:
            logger.error(f"SQL验证错误: {e}")
            return {
                "is_safe": False,
                "sanitized_sql": sql,
                "reason": f"SQL解析错误: {str(e)}"
            }

    def _sanitize_sql(self, parsed) -> str:
        """
        清理SQL，添加LIMIT（如果不存在）

        Args:
            parsed: 解析后的SQL AST

        Returns:
            清理后的SQL语句
        """
        sql = parsed.sql(dialect="duckdb")

        # 如果没有LIMIT，自动添加
        if "LIMIT" not in sql.upper():
            sql = f"{sql} LIMIT {self.max_rows}"

        return sql

# 全局SQL Guard实例
sql_guard = SQLGuard()