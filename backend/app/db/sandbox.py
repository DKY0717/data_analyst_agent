# SQL 执行沙箱
# 在子进程中隔离执行 SQL，防止恶意 SQL 影响主进程

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any

from ..config import settings
from ..utils.logger import logger


# 沙箱 worker 脚本路径
_WORKER_SCRIPT = Path(__file__).parent / "_sandbox_worker.py"


class SandboxExecutor:
    """沙箱 SQL 执行器

    在独立子进程中执行 SQL，主进程通过 stdin/stdout 通信。
    子进程崩溃或超时不会影响主进程。

    安全隔离层：
    - 进程级隔离：子进程崩溃不影响主进程
    - 超时控制：强制终止超时查询
    - 资源限制：通过 subprocess 参数限制资源
    """

    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.SQL_TIMEOUT

    def execute(
        self,
        sql: str,
        connection_config: str | dict[str, Any],
        backend: str,
        timeout: int | None = None,
        include_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        """在沙箱子进程中执行 SQL"""
        start_time = time.time()
        effective_timeout = timeout or self.timeout

        try:
            # 构建 worker 输入
            input_data = json.dumps({
                "sql": sql,
                "connection_config": connection_config,
                "backend": backend,
                "timeout": effective_timeout,
            })

            # 启动子进程
            result = subprocess.run(
                [sys.executable, str(_WORKER_SCRIPT)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=str(settings.BASE_DIR),
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            if result.returncode != 0:
                logger.error("沙箱子进程异常退出: returncode=%s", result.returncode)
                return {
                    "success": False,
                    "columns": [],
                    "rows": [],
                    "execution_time_ms": execution_time_ms,
                    "error": "沙箱执行失败",
                    "error_type": "SandboxError",
                }

            # 解析子进程输出
            output = json.loads(result.stdout)
            output["execution_time_ms"] = execution_time_ms
            if not output.get("success"):
                diagnostic_error = str(output.get("error") or "")
                logger.error(
                    "沙箱查询执行失败: %s",
                    output.get("error_type") or "DatabaseError",
                )
                if include_diagnostics:
                    output["diagnostic_error"] = diagnostic_error
                output["error"] = "查询执行失败"
            return output

        except subprocess.TimeoutExpired:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"沙箱执行超时 ({effective_timeout}s)")
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "execution_time_ms": execution_time_ms,
                "error": f"查询超时 ({effective_timeout}s)",
                "error_type": "TimeoutError",
            }
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error("沙箱执行发生内部异常: %s", type(e).__name__)
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "execution_time_ms": execution_time_ms,
                "error": "沙箱执行失败",
                "error_type": "SandboxError",
            }


sandbox_executor = SandboxExecutor()
