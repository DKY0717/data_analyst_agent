# SQL查询执行模块
# 支持 DuckDB 和 PostgreSQL 双后端
# 支持直接执行和沙箱隔离执行两种模式

import time
from typing import Dict, Any

from ..config import settings
from ..utils.logger import logger
from ..utils.exceptions import SQLExecutionError
from .connection import db_connection
from .sandbox import sandbox_executor


class QueryRunner:
    """SQL查询执行器（双后端 + 沙箱支持）

    通过 SANDBOX_MODE 环境变量控制执行模式：
    - true: 沙箱模式，在子进程中隔离执行（生产推荐）
    - false: 直接模式，在主进程中执行（开发调试）
    """

    def __init__(self, timeout: int = None, sandbox: bool | None = None):
        self.timeout = timeout or settings.SQL_TIMEOUT
        self.sandbox = settings.SANDBOX_MODE if sandbox is None else sandbox

    def execute(self, sql: str) -> Dict[str, Any]:
        """执行SQL查询"""
        if self.sandbox:
            return self._execute_sandbox(sql)
        return self._execute_direct(sql)

    def _execute_sandbox(self, sql: str) -> Dict[str, Any]:
        """沙箱模式：在子进程中执行"""
        db_path = str(settings.DATA_DIR / "database.duckdb")
        return sandbox_executor.execute(sql, db_path, db_connection.backend)

    def _execute_direct(self, sql: str) -> Dict[str, Any]:
        """直接模式：在主进程中执行"""
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
