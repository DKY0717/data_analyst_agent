# SQL安全校验模块
# 使用SQLGlot进行SQL AST解析，验证SQL语句的安全性

import sqlglot
from sqlglot import exp
from typing import Dict, Any, Optional, Tuple, List

from ..utils.logger import logger
from ..utils.exceptions import SQLGuardError
from ..config import settings
from ..agents.audit import audit_report_builder
from ..db.connection import db_connection


class SQLGuard:
    """SQL安全校验器（支持 DuckDB 和 PostgreSQL 方言）"""

    # 允许的语句类型
    ALLOWED_STATEMENTS = {"SELECT", "WITH", "EXPLAIN"}

    # 禁止的语句类型
    BLOCKED_STATEMENTS = {
        "DROP", "DELETE", "UPDATE", "INSERT",
        "ALTER", "TRUNCATE", "CREATE", "MERGE",
        "CALL", "EXECUTE", "GRANT", "REVOKE"
    }

    # DuckDB 特有的危险 Command（SQLGlot 解析为 Command 类型）
    BLOCKED_COMMANDS = {"COPY", "ATTACH", "DETACH", "EXPORT", "IMPORT"}

    # 系统 Schema 和系统表通常包含数据库内部元数据，不应该暴露给自然语言查询入口
    BLOCKED_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog"}
    BLOCKED_TABLE_PREFIXES = ("duckdb_", "pg_")

    # DuckDB 支持通过 SELECT 调用文件/元数据函数；这些函数即使是 SELECT 也可能造成数据外泄
    BLOCKED_FUNCTIONS = {
        "read_csv", "read_csv_auto", "read_json", "read_json_auto",
        "read_ndjson", "read_parquet", "read_text", "read_blob",
        "glob", "duckdb_tables", "duckdb_columns", "duckdb_views",
        "duckdb_schemas", "duckdb_databases", "duckdb_settings",
        "duckdb_functions", "duckdb_indexes", "duckdb_constraints",
    }

    def __init__(self, max_rows: int = None):
        """
        初始化SQL Guard

        Args:
            max_rows: 最大返回行数，默认使用配置中的SQL_MAX_ROWS
        """
        self.max_rows = max_rows or settings.SQL_MAX_ROWS
        self._dialect = "postgres" if db_connection.backend == "postgresql" else "duckdb"

    def validate(self, sql: str) -> Dict[str, Any]:
        """
        验证SQL安全性

        Args:
            sql: SQL语句

        Returns:
            包含is_safe、sanitized_sql、reason的字典
        """
        try:
            audit_events: List[Dict[str, Any]] = []

            # 模型拒绝危险请求时可能返回空 SQL；在 AST 解析前给出稳定、可审计的阻断结果。
            if not sql or not sql.strip():
                return self._result(
                    False,
                    sql or "",
                    "SQL 为空",
                    audit_events,
                    blocked_rule="block_empty_sql",
                )

            # 先解析全部语句，避免 parse_one 只取第一条导致多语句绕过
            statements = sqlglot.parse(sql, dialect=self._dialect)
            if len(statements) != 1:
                return self._result(
                    False,
                    sql,
                    "不允许执行多个语句",
                    audit_events,
                    blocked_rule="block_multi_statement",
                )

            parsed = statements[0]

            # 检查语句类型
            statement_type = self._get_statement_type(parsed)

            if statement_type not in self.ALLOWED_STATEMENTS:
                if statement_type in self.BLOCKED_STATEMENTS:
                    return self._result(
                        False,
                        sql,
                        f"禁止的语句类型: {statement_type}",
                        audit_events,
                        blocked_rule="block_statement_type",
                        details={"statement_type": statement_type},
                    )
                else:
                    return self._result(
                        False,
                        sql,
                        f"未知的语句类型: {statement_type}",
                        audit_events,
                        blocked_rule="block_unknown_statement",
                        details={"statement_type": statement_type},
                    )

            # EXPLAIN 在 DuckDB 中会被 SQLGlot 解析为 Command，需要单独取出内部 SELECT 再校验
            ast_for_safety = self._extract_explain_query(parsed) if statement_type == "EXPLAIN" else parsed

            security_error, blocked_rule = self._validate_ast_safety(ast_for_safety)
            if security_error:
                return self._result(
                    False,
                    sql,
                    security_error,
                    audit_events,
                    blocked_rule=blocked_rule,
                )

            # 清理SQL
            sanitized_sql, limit_injected = self._sanitize_sql(parsed, statement_type)
            if limit_injected:
                audit_events.append(
                    audit_report_builder.make_event(
                        "guard",
                        "inject_limit",
                        "success",
                        f"查询缺少 LIMIT，已自动注入 LIMIT {self.max_rows}",
                        rule_id="limit_injected",
                        details={"limit_injected": True, "max_rows": self.max_rows},
                    )
                )

            audit_events.append(
                audit_report_builder.make_event(
                    "guard",
                    "validate_sql",
                    "success",
                    "SQL 通过安全校验",
                    details={"limit_injected": limit_injected},
                )
            )

            return {
                "is_safe": True,
                "sanitized_sql": sanitized_sql,
                "reason": None,
                "audit_events": audit_events,
                "limit_injected": limit_injected,
                "blocked_rule": None,
            }

        except Exception as e:
            logger.error(f"SQL验证错误: {e}")
            return self._result(
                False,
                sql,
                f"SQL解析错误: {str(e)}",
                [],
                blocked_rule="parse_error",
            )

    def _result(
        self,
        is_safe: bool,
        sanitized_sql: str,
        reason: Optional[str],
        audit_events: List[Dict[str, Any]],
        blocked_rule: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """统一构造 Guard 返回值，确保成功和失败都有审计字段。"""
        if not is_safe:
            audit_events = audit_events + [
                audit_report_builder.make_event(
                    "guard",
                    "validate_sql",
                    "blocked",
                    reason or "SQL 未通过安全校验",
                    rule_id=blocked_rule,
                    details=details,
                )
            ]

        return {
            "is_safe": is_safe,
            "sanitized_sql": sanitized_sql,
            "reason": reason,
            "audit_events": audit_events,
            "limit_injected": False,
            "blocked_rule": blocked_rule,
        }

    def _get_statement_type(self, parsed) -> str:
        """识别语句类型，兼容 DuckDB 命令被解析成 Command 的情况"""
        if isinstance(parsed, exp.Command):
            cmd = str(parsed.this).upper()
            if cmd == "EXPLAIN":
                return "EXPLAIN"
            if cmd in self.BLOCKED_COMMANDS:
                return cmd
        return parsed.key.upper()

    def _extract_explain_query(self, parsed):
        """从 EXPLAIN 命令中提取内部查询，确保优化分析也不能绕过安全规则"""
        expression = parsed.args.get("expression")
        if not expression:
            raise SQLGuardError("EXPLAIN 缺少内部查询")
        return sqlglot.parse_one(str(expression.this), dialect=self._dialect)

    def _validate_ast_safety(self, parsed) -> Tuple[Optional[str], Optional[str]]:
        """遍历 SQL AST，拦截 SELECT 形式的数据外泄路径"""
        for table in parsed.find_all(exp.Table):
            table_name = (table.name or "").lower()
            schema_name = (table.db or "").lower()

            if schema_name in self.BLOCKED_SYSTEM_SCHEMAS:
                return f"禁止访问系统表: {table.sql(dialect=self._dialect)}", "block_system_schema"

            if table_name.startswith(self.BLOCKED_TABLE_PREFIXES):
                return f"禁止访问系统表: {table.sql(dialect=self._dialect)}", "block_system_table"

        for func in parsed.find_all(exp.Func):
            function_name = (getattr(func, "name", "") or "").lower()
            if function_name in self.BLOCKED_FUNCTIONS:
                return f"禁止调用危险函数: {function_name}", "block_dangerous_function"

        return None, None

    def _sanitize_sql(self, parsed, statement_type: str) -> Tuple[str, bool]:
        """
        清理SQL，添加LIMIT（如果不存在）

        Args:
            parsed: 解析后的SQL AST
            statement_type: 已识别的语句类型

        Returns:
            清理后的SQL语句
        """
        if statement_type == "EXPLAIN":
            return parsed.sql(dialect=self._dialect), False

        # 使用 AST 判断顶层 LIMIT，避免字符串字面量或字段名里的 LIMIT 误导安全逻辑
        limit_injected = False
        if not parsed.args.get("limit"):
            parsed = parsed.limit(self.max_rows)
            limit_injected = True

        return parsed.sql(dialect=self._dialect), limit_injected

# 全局SQL Guard实例
sql_guard = SQLGuard()
