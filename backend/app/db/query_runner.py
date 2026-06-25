# SQL查询执行模块
# 支持 DuckDB 和 PostgreSQL 双后端

import time
from typing import Dict, Any

from ..config import settings
from ..utils.logger import logger
from ..utils.exceptions import SQLExecutionError
from .connection import db_connection


class QueryRunner:
    """SQL查询执行器（双后端支持）"""

    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.SQL_TIMEOUT

    def execute(self, sql: str) -> Dict[str, Any]:
        """执行SQL查询"""
        start_time = time.time()

        try:
            with db_connection.get_session() as conn:
                if db_connection.backend == "postgresql":
                    cur = conn.cursor()
                    cur.execute(sql)
                    columns = [desc[0] for desc in cur.description] if cur.description else []
                    rows = [list(row) for row in cur.fetchall()]
                else:
                    result = conn.execute(sql)
                    columns = [desc[0] for desc in result.description] if result.description else []
                    rows = [list(row) for row in result.fetchall()]

                execution_time_ms = int((time.time() - start_time) * 1000)
                logger.info(f"查询执行成功，返回 {len(rows)} 行，耗时 {execution_time_ms}ms")

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "execution_time_ms": execution_time_ms,
                    "row_count": len(rows),
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
                "error_type": error_type,
            }


query_runner = QueryRunner()
