"""安全执行黄金基准参考 SQL，并返回稳定的结构化结果。"""

from typing import Any, Dict, Optional

from app.db.query_runner import query_runner
from app.security.sql_guard import sql_guard
from app.utils.logger import logger


class ReferenceQueryRunner:
    """通过现有 SQL Guard 执行参考 SQL，避免黄金 case 绕过安全治理。"""

    def __init__(self, guard=sql_guard, query_runner=query_runner):
        self.guard = guard
        self.query_runner = query_runner

    def run(self, reference_sql: str) -> Dict[str, Any]:
        """校验并执行参考 SQL；所有失败都转换为稳定结果，不向调用方抛异常。"""
        guard_passed = False
        sanitized_sql = ""

        try:
            # 参考 SQL 也必须经过 Guard，执行器只能接收 Guard 清洗后的 SQL。
            guard_result = self.guard.validate(reference_sql)
            guard_payload = guard_result if isinstance(guard_result, dict) else {}
            guard_sanitized_sql = guard_payload.get("sanitized_sql", "")
            sanitized_sql = guard_sanitized_sql if isinstance(guard_sanitized_sql, str) else ""
            # Guard 契约必须精确满足安全标记和非空 SQL，任何畸形返回都按阻断处理。
            guard_passed = (
                guard_payload.get("is_safe") is True
                and isinstance(guard_sanitized_sql, str)
                and bool(guard_sanitized_sql.strip())
            )

            if not guard_passed:
                return self._result(
                    sanitized_sql=sanitized_sql,
                    error=guard_payload.get("reason") or "参考 SQL 未通过安全校验",
                    error_type="reference_guard_blocked",
                )

            execution_result = self.query_runner.execute(sanitized_sql)
            if not execution_result.get("success"):
                return self._result(
                    guard_passed=True,
                    sanitized_sql=sanitized_sql,
                    error=execution_result.get("error") or "参考 SQL 执行失败",
                    error_type="reference_execution_failed",
                )

            columns = execution_result.get("columns") or []
            rows = execution_result.get("rows") or []
            row_count = execution_result.get("row_count", len(rows))

            # 日志只记录行数，不输出完整结果集，避免黄金数据被日志意外泄露。
            logger.info(f"参考 SQL 执行成功，返回 {row_count} 行")
            return self._result(
                guard_passed=True,
                execution_success=True,
                columns=columns,
                rows=rows,
                row_count=row_count,
                sanitized_sql=sanitized_sql,
            )
        except Exception as exc:
            # 意外异常可能携带凭据或数据库细节，日志和返回值只保留稳定摘要。
            logger.error("参考 SQL 执行发生意外异常，异常类型=%s", type(exc).__name__)
            return self._result(
                guard_passed=guard_passed,
                sanitized_sql=sanitized_sql,
                error="参考 SQL 执行发生意外异常",
                error_type="reference_unexpected_error",
            )

    @staticmethod
    def _result(
        *,
        guard_passed: bool = False,
        execution_success: bool = False,
        columns: Optional[list] = None,
        rows: Optional[list] = None,
        row_count: int = 0,
        sanitized_sql: str = "",
        error: Optional[str] = None,
        error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """集中构造结果，确保成功、阻断和异常路径拥有相同字段。"""
        return {
            "guard_passed": guard_passed,
            "execution_success": execution_success,
            "columns": columns or [],
            "rows": rows or [],
            "row_count": row_count,
            "sanitized_sql": sanitized_sql,
            "error": error,
            "error_type": error_type,
        }


reference_query_runner = ReferenceQueryRunner()
