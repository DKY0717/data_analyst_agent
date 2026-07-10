# 数据权限 Guard
# 在 SQL Guard 确认语句安全后，继续检查“这个用户能不能看这些表和字段”。

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

from ..agents.audit import audit_report_builder
from ..utils.logger import logger
from .permission_policy import (
    ALL_COLUMNS,
    PermissionPolicyError,
    PermissionPolicyLoader,
    RowFilterPolicy,
    TablePolicy,
)


@dataclass(frozen=True)
class PermissionUser:
    """权限检查只需要最小身份摘要，避免把 Token 或请求头带入 AgentState。"""

    user_id: str
    auth_method: str
    roles: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DataPermissionResult:
    """权限 Guard 的稳定返回结构，便于 AgentGraph 和测试直接消费。"""

    is_allowed: bool
    reason: str
    blocked_rule: str | None
    audit_events: list[dict[str, Any]]
    referenced_tables: list[str]
    referenced_columns: list[str]
    authorized_sql: str
    row_filters_applied: list[dict[str, Any]]


class DataPermissionGuard:
    """基于最终 SQL AST 做表级和字段级授权。

    该 Guard 放在 SQL Guard 之后、QueryRunner 之前。它不尝试修复 SQL，也不访问数据库，
    因为权限判断必须是确定性的安全边界。
    """

    def authorize(
        self,
        sql: str,
        user: dict[str, Any] | PermissionUser | None,
        schema: dict[str, Any] | None = None,
    ) -> DataPermissionResult:
        """检查 SQL 引用的表和字段是否符合当前用户角色。"""
        permission_user = self._normalize_user(user)

        try:
            parsed = sqlglot.parse_one(sql, dialect="duckdb")
        except Exception as exc:
            logger.warning("数据权限 SQL 解析失败")
            return self._blocked(
                "SQL 权限解析失败",
                "block_permission_parse_error",
                permission_user,
                [],
                [],
                details={"error_type": type(exc).__name__},
            )

        schema_columns = self._columns_by_table_from_schema(schema)
        cte_names = self._cte_names(parsed)
        table_aliases, referenced_tables = self._referenced_tables(parsed, cte_names)
        referenced_columns, column_error = self._referenced_columns(
            parsed,
            referenced_tables,
            table_aliases,
            schema_columns,
        )
        if column_error:
            return self._blocked(
                column_error["reason"],
                column_error["rule_id"],
                permission_user,
                referenced_tables,
                referenced_columns,
                details=column_error.get("details"),
            )

        try:
            allowed_tables = self._allowed_tables(permission_user.roles)
        except PermissionPolicyError as exc:
            return self._blocked(
                "权限策略加载失败",
                "block_permission_policy_error",
                permission_user,
                referenced_tables,
                referenced_columns,
                details={"error_type": type(exc).__name__},
            )

        for table in referenced_tables:
            if table not in allowed_tables and ALL_COLUMNS not in allowed_tables:
                return self._blocked(
                    f"当前角色无权访问表: {table}",
                    "block_unauthorized_table",
                    permission_user,
                    referenced_tables,
                    referenced_columns,
                    details={"table": table},
                )

        for qualified_column in referenced_columns:
            table, column = qualified_column.split(".", 1)
            table_policy = allowed_tables.get(table) or allowed_tables.get(ALL_COLUMNS)
            allowed_columns = table_policy.columns if table_policy else None
            if allowed_columns is None or (
                ALL_COLUMNS not in allowed_columns and column not in allowed_columns
            ):
                return self._blocked(
                    f"当前角色无权访问字段: {qualified_column}",
                    "block_unauthorized_column",
                    permission_user,
                    referenced_tables,
                    referenced_columns,
                    details={"table": table, "column": column},
                )

        authorized_sql, row_filters_applied, row_filter_error = self._apply_row_filters(
            sql,
            parsed,
            referenced_tables,
            allowed_tables,
        )
        if row_filter_error:
            return self._blocked(
                row_filter_error["reason"],
                row_filter_error["rule_id"],
                permission_user,
                referenced_tables,
                referenced_columns,
                details=row_filter_error.get("details"),
            )

        return self._allowed(
            permission_user,
            referenced_tables,
            referenced_columns,
            authorized_sql,
            row_filters_applied,
        )

    def _normalize_user(self, user: dict[str, Any] | PermissionUser | None) -> PermissionUser:
        """把 API 层传入的身份压缩成权限模块需要的最小形式。"""
        if user is None:
            return PermissionUser(
                user_id="dev:anonymous",
                auth_method="disabled",
                roles=["admin"],
            )
        if isinstance(user, PermissionUser):
            permission_user = user
        else:
            permission_user = PermissionUser(
                user_id=str(user.get("user_id") or "unknown"),
                auth_method=str(user.get("auth_method") or "unknown"),
                roles=list(user.get("roles") or []),
            )

        roles = permission_user.roles
        if permission_user.auth_method == "api_key" and (not roles or roles == ["user"]):
            roles = ["analyst"]
        return PermissionUser(
            user_id=permission_user.user_id,
            auth_method=permission_user.auth_method,
            roles=roles,
        )

    def _allowed_tables(self, roles: list[str]) -> dict[str, TablePolicy]:
        """多个角色取权限并集；未知角色不授予任何隐式权限。"""
        policy = PermissionPolicyLoader().load()
        allowed: dict[str, TablePolicy] = {}
        for role in roles:
            role_policy = policy.roles.get(role)
            if role_policy is None:
                continue
            for table, table_policy in role_policy.tables.items():
                existing = allowed.get(table)
                if existing is None:
                    allowed[table] = table_policy
                    continue
                allowed[table] = TablePolicy(
                    columns=set(existing.columns).union(table_policy.columns),
                    row_filter=existing.row_filter or table_policy.row_filter,
                )
        return allowed

    def _columns_by_table_from_schema(self, schema: dict[str, Any] | None) -> dict[str, set[str]]:
        """支持 SchemaLoader 当前输出格式，用于解析裸列归属。"""
        tables = (schema or {}).get("tables") or {}
        columns_by_table: dict[str, set[str]] = {}
        for table_name, table_info in tables.items():
            columns = table_info.get("columns") or []
            column_names = {
                str(column.get("name", "")).lower()
                for column in columns
                if isinstance(column, dict) and column.get("name")
            }
            columns_by_table[str(table_name).lower()] = column_names
        return columns_by_table

    def _cte_names(self, parsed: exp.Expression) -> set[str]:
        """CTE 名称不是物理表，权限检查应落到 CTE 内部真实表上。"""
        return {
            str(cte.alias_or_name).lower()
            for cte in parsed.find_all(exp.CTE)
            if cte.alias_or_name
        }

    def _referenced_tables(
        self,
        parsed: exp.Expression,
        cte_names: set[str],
    ) -> tuple[dict[str, str], list[str]]:
        """提取物理表和别名映射，后续列权限依赖这个映射还原真实表。"""
        alias_to_table: dict[str, str] = {}
        referenced: list[str] = []
        for table in parsed.find_all(exp.Table):
            table_name = (table.name or "").lower()
            if not table_name or table_name in cte_names:
                continue
            if table_name not in referenced:
                referenced.append(table_name)
            alias_to_table[(table.alias_or_name or table_name).lower()] = table_name
            alias_to_table[table_name] = table_name
        return alias_to_table, referenced

    def _referenced_columns(
        self,
        parsed: exp.Expression,
        referenced_tables: list[str],
        table_aliases: dict[str, str],
        schema_columns: dict[str, set[str]],
    ) -> tuple[list[str], dict[str, Any] | None]:
        """提取字段引用；多表裸列无法可靠归属时采用 fail-closed。"""
        referenced_columns: list[str] = []

        for star in parsed.find_all(exp.Star):
            if self._is_count_star(star):
                continue
            table = self._resolve_star_table(star, referenced_tables, table_aliases)
            if table is None:
                return referenced_columns, {
                    "rule_id": "block_ambiguous_column",
                    "reason": "无法唯一判断通配字段归属: *",
                    "details": {"column": "*"},
                }
            self._append_unique(referenced_columns, f"{table}.{ALL_COLUMNS}")

        for column in parsed.find_all(exp.Column):
            table_name = self._resolve_column_table(
                column,
                referenced_tables,
                table_aliases,
                schema_columns,
            )
            if table_name is None:
                return referenced_columns, {
                    "rule_id": "block_ambiguous_column",
                    "reason": f"无法唯一判断字段归属: {column.name}",
                    "details": {"column": column.name},
                }
            self._append_unique(referenced_columns, f"{table_name}.{column.name.lower()}")

        return referenced_columns, None

    def _is_count_star(self, star: exp.Star) -> bool:
        """COUNT(*) 不暴露具体列，不能像 SELECT * 一样按字段泄露处理。"""
        parent = star.parent
        return isinstance(parent, exp.Count) or (
            isinstance(parent, exp.Anonymous) and str(parent.name).lower() == "count"
        )

    def _resolve_star_table(
        self,
        star: exp.Star,
        referenced_tables: list[str],
        table_aliases: dict[str, str],
    ) -> str | None:
        table = getattr(star, "table", "") or ""
        if table:
            return table_aliases.get(table.lower(), table.lower())
        if len(referenced_tables) == 1:
            return referenced_tables[0]
        return None

    def _resolve_column_table(
        self,
        column: exp.Column,
        referenced_tables: list[str],
        table_aliases: dict[str, str],
        schema_columns: dict[str, set[str]],
    ) -> str | None:
        explicit_table = (column.table or "").lower()
        if explicit_table:
            return table_aliases.get(explicit_table, explicit_table)

        if len(referenced_tables) == 1:
            return referenced_tables[0]

        matches = [
            table
            for table in referenced_tables
            if column.name.lower() in schema_columns.get(table, set())
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def _apply_row_filters(
        self,
        sql: str,
        parsed: exp.Expression,
        referenced_tables: list[str],
        allowed_tables: dict[str, TablePolicy],
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any] | None]:
        """对命中策略的表注入行级过滤；无法安全改写时 fail-closed。"""
        rewritten = parsed.copy()
        cte_names = self._cte_names(rewritten)
        filters: list[tuple[str, exp.Select, RowFilterPolicy]] = []
        applied_policies: list[tuple[str, RowFilterPolicy]] = []

        for table in referenced_tables:
            table_policy = allowed_tables.get(table) or allowed_tables.get(ALL_COLUMNS)
            if table_policy and table_policy.row_filter:
                table_occurrences = [
                    table_expression
                    for table_expression in rewritten.find_all(exp.Table)
                    if (table_expression.name or "").lower() == table
                    and (table_expression.name or "").lower() not in cte_names
                ]
                if not table_occurrences:
                    return sql, [], {
                        "rule_id": "block_row_filter_unsupported",
                        "reason": f"无法安全应用行级权限过滤: {table}",
                        "details": {"table": table},
                    }

                for table_expression in table_occurrences:
                    select_scope = table_expression.find_ancestor(exp.Select)
                    if select_scope is None:
                        return sql, [], {
                            "rule_id": "block_row_filter_unsupported",
                            "reason": f"无法定位行级权限过滤作用域: {table}",
                            "details": {"table": table},
                        }
                    alias = (table_expression.alias_or_name or table).lower()
                    filters.append((alias, select_scope, table_policy.row_filter))
                applied_policies.append((table, table_policy.row_filter))

        if not filters:
            return sql, [], None

        try:
            for alias, select_scope, row_filter in filters:
                predicate = self._qualified_filter_expression(row_filter.expression, alias)
                existing_where = select_scope.args.get("where")
                if existing_where is None:
                    select_scope.set("where", exp.Where(this=predicate))
                else:
                    select_scope.set(
                        "where",
                        exp.Where(this=exp.and_(existing_where.this, predicate)),
                    )
            applied = [
                {"table": table, "rule_id": row_filter.rule_id}
                for table, row_filter in applied_policies
            ]
            return rewritten.sql(dialect="duckdb"), applied, None
        except Exception as exc:
            logger.warning("行级权限 SQL 改写失败")
            return sql, [], {
                "rule_id": "block_row_filter_unsupported",
                "reason": "行级权限过滤无法安全应用",
                "details": {"error_type": type(exc).__name__},
            }

    def _qualified_filter_expression(self, expression: str, alias: str) -> exp.Expression:
        """只限定行过滤表达式顶层目标表字段，保留子查询内部字段归属。"""
        predicate = sqlglot.parse_one(expression, dialect="duckdb", into=exp.Condition)
        for column in predicate.find_all(exp.Column):
            if column.table or column.find_ancestor(exp.Select):
                continue
            column.set("table", exp.to_identifier(alias))
        return predicate

    def _allowed(
        self,
        user: PermissionUser,
        referenced_tables: list[str],
        referenced_columns: list[str],
        authorized_sql: str,
        row_filters_applied: list[dict[str, Any]],
    ) -> DataPermissionResult:
        has_row_filters = bool(row_filters_applied)
        return DataPermissionResult(
            is_allowed=True,
            reason="SQL 通过数据权限检查",
            blocked_rule=None,
            audit_events=[
                self._event(
                    "success",
                    "SQL 通过数据权限检查",
                    user,
                    referenced_tables,
                    referenced_columns,
                    rule_id="row_filter_applied" if has_row_filters else None,
                    row_filters_applied=row_filters_applied,
                    authorized_sql_changed=has_row_filters,
                )
            ],
            referenced_tables=referenced_tables,
            referenced_columns=referenced_columns,
            authorized_sql=authorized_sql,
            row_filters_applied=row_filters_applied,
        )

    def _blocked(
        self,
        reason: str,
        rule_id: str,
        user: PermissionUser,
        referenced_tables: list[str],
        referenced_columns: list[str],
        details: dict[str, Any] | None = None,
    ) -> DataPermissionResult:
        return DataPermissionResult(
            is_allowed=False,
            reason=reason,
            blocked_rule=rule_id,
            audit_events=[
                self._event("blocked", reason, user, referenced_tables, referenced_columns, rule_id, details)
            ],
            referenced_tables=referenced_tables,
            referenced_columns=referenced_columns,
            authorized_sql="",
            row_filters_applied=[],
        )

    def _event(
        self,
        status: str,
        message: str,
        user: PermissionUser,
        referenced_tables: list[str],
        referenced_columns: list[str],
        rule_id: str | None = None,
        details: dict[str, Any] | None = None,
        row_filters_applied: list[dict[str, Any]] | None = None,
        authorized_sql_changed: bool = False,
    ) -> dict[str, Any]:
        """审计事件只记录决策证据，不泄露完整策略或凭证。"""
        event_details = {
            "user_id": user.user_id,
            "auth_method": user.auth_method,
            "roles": user.roles,
            "tables": referenced_tables,
            "columns_checked": referenced_columns,
            "row_filters_applied": row_filters_applied or [],
            "authorized_sql_changed": authorized_sql_changed,
        }
        event_details.update(details or {})
        return audit_report_builder.make_event(
            "authorization",
            "authorize_sql",
            status,
            message,
            rule_id=rule_id,
            details=event_details,
        )

    @staticmethod
    def _append_unique(values: list[str], value: str) -> None:
        if value not in values:
            values.append(value)


data_permission_guard = DataPermissionGuard()
