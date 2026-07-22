# SQL查询执行模块
# 支持 DuckDB 和 PostgreSQL 双后端
# 支持直接执行和沙箱隔离执行两种模式

import time
from typing import Dict, Any

from ..config import settings
from ..utils.logger import logger
from .connection import db_connection
from .sandbox import sandbox_executor


class QueryRunner:
    """SQL查询执行器（双后端 + 沙箱支持）

    通过 SANDBOX_MODE 环境变量控制执行模式：
    - true: 沙箱模式，在子进程中隔离执行（生产推荐）
    - false: 直接模式，在主进程中执行（开发调试）
    """

    def __init__(
        self,
        timeout: int = None,
        sandbox: bool | None = None,
        connection=None,
    ):
        self.timeout = timeout or settings.SQL_TIMEOUT
        self.sandbox = settings.SANDBOX_MODE if sandbox is None else sandbox
        self._connection = connection

    @property
    def connection(self):
        """默认动态读取全局连接，保留现有 mock 和运行时后端切换能力。"""
        return self._connection or db_connection

    def execute(self, sql: str) -> Dict[str, Any]:
        """执行SQL查询"""
        if self.sandbox:
            return self._execute_sandbox(sql)
        return self._execute_direct(sql)

    def _execute_sandbox(self, sql: str) -> Dict[str, Any]:
        """沙箱模式：在子进程中执行"""
        connection_config = self._sandbox_connection_config()
        result = sandbox_executor.execute(
            sql,
            connection_config,
            self.connection.backend,
            timeout=self.timeout,
            include_diagnostics=True,
        )
        result["execution_mode"] = "sandbox"
        return result

    def _sandbox_connection_config(self) -> str | dict[str, Any]:
        """按数据库后端生成沙箱子进程可用的连接配置。"""
        if self.connection.backend == "postgresql":
            # PostgreSQL 沙箱必须拿到 PG 连接参数，不能复用 DuckDB 的本地文件路径。
            return {
                "host": settings.PG_HOST,
                "port": settings.PG_PORT,
                "user": settings.PG_USER,
                "password": settings.PG_PASSWORD,
                "dbname": settings.PG_DATABASE,
            }
        custom_path = getattr(self.connection, "db_path", None)
        return str(custom_path or settings.DATA_DIR / "database.duckdb")

    def _execute_direct(self, sql: str) -> Dict[str, Any]:
        """直接模式：在主进程中执行"""
        start_time = time.time()

        try:
            with self.connection.get_session() as conn:
                if self.connection.backend == "postgresql":
                    cur = conn.cursor()
                    # set_config(..., true) 仅作用于当前事务，避免污染连接或其他请求。
                    cur.execute(
                        "SELECT set_config('statement_timeout', %s, true)",
                        (f"{self.timeout}s",),
                    )
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
                    "execution_mode": "direct",
                }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            error_type = type(e).__name__

            logger.error("查询执行失败: %s，耗时 %sms", error_type, execution_time_ms)

            return {
                "success": False,
                "columns": [],
                "rows": [],
                "execution_time_ms": execution_time_ms,
                "error": "查询执行失败",
                "diagnostic_error": error_msg,
                "error_type": error_type,
                "execution_mode": "direct",
            }


query_runner = QueryRunner()
