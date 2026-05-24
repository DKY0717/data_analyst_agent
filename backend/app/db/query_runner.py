# SQL查询执行模块
# 执行已通过安全校验的SQL语句，返回结构化结果

import time
from typing import Dict, Any, List

from ..config import settings
from ..utils.logger import logger
from ..utils.exceptions import SQLExecutionError
from .connection import db_connection


class QueryRunner:
    """SQL查询执行器"""

    def __init__(self, timeout: int = None):
        """
        初始化查询执行器

        Args:
            timeout: 查询超时时间（秒），默认使用配置中的SQL_TIMEOUT
        """
        self.timeout = timeout or settings.SQL_TIMEOUT

    def execute(self, sql: str) -> Dict[str, Any]:
        """
        执行SQL查询

        Args:
            sql: SQL语句（应已通过SQL Guard校验）

        Returns:
            包含success、columns、rows、execution_time_ms等字段的字典
        """
        start_time = time.time()

        try:
            with db_connection.get_session() as conn:
                # 执行SQL（DuckDB不支持statement_timeout，超时由应用层控制）
                result = conn.execute(sql)

                # 提取列名
                columns = [desc[0] for desc in result.description] if result.description else []

                # 提取数据行，将元组转为列表
                rows = [list(row) for row in result.fetchall()]

                # 计算执行时间
                execution_time_ms = int((time.time() - start_time) * 1000)

                logger.info(f"查询执行成功，返回 {len(rows)} 行，耗时 {execution_time_ms}ms")

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "execution_time_ms": execution_time_ms,
                    "row_count": len(rows)
                }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            error_type = type(e).__name__

            logger.error(f"查询执行失败: {error_type}: {error_msg}，耗时 {execution_time_ms}ms")

            return {
                "success": False,
                "columns": [],
                "rows": [],
                "execution_time_ms": execution_time_ms,
                "error": error_msg,
                "error_type": error_type
            }


# 全局查询执行器实例
query_runner = QueryRunner()
