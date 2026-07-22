# 数据权限 Guard
# 在 SQL Guard 确认语句安全后，继续检查“这个用户能不能看这些表和字段”。

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

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
        referenced_tables = self._referenced_tables(parsed, cte_names)
        referenced_columns, column_error = self._referenced_columns(
            parsed,
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
    ) -> list[str]:
        """提取物理表；CTE 名称由作用域解析，不应进入策略表集合。"""
        referenced: list[str] = []
        for table in parsed.find_all(exp.Table):
            table_name = (table.name or "").lower()
            if not table_name or table_name in cte_names:
                continue
            if table_name not in referenced:
                referenced.append(table_name)
        return referenced

    def _referenced_columns(
        self,
        parsed: exp.Expression,
        schema_columns: dict[str, set[str]],
    ) -> tuple[list[str], dict[str, Any] | None]:
        """按查询作用域提取物理字段；派生输出由它的子作用域负责检查。"""
        referenced_columns: list[str] = []

        try:
            scopes = traverse_scope(parsed)
            for scope in scopes:
                # 每个 Star 只归属于最近的 SELECT，避免父 scope 重复遍历子查询内容。
                for star in self._stars_in_scope(scope):
                    if self._is_count_star(star):
                        continue
                    table, is_derived = self._resolve_scope_star(scope, star)
                    if is_derived:
                        continue
                    if table is None:
                        return referenced_columns, self._ambiguous_column_error("*")
                    self._append_unique(referenced_columns, f"{table}.{ALL_COLUMNS}")

                for column in scope.columns:
                    # 相关子查询的外部列还会出现在父 scope；这里只在真实来源处检查一次。
                    is_qualified_external = (
                        scope.parent is not None
                        and bool(column.table)
                        and column in scope.external_columns
                    )
                    if is_qualified_external or self._is_projection_alias_reference(column):
                        continue
                    table, is_derived = self._resolve_scope_column(
                        scope,
                        column,
                        schema_columns,
                    )
                    if is_derived:
                        continue
                    if table is None:
                        return referenced_columns, self._ambiguous_column_error(column.name)
                    self._append_unique(
                        referenced_columns,
                        f"{table}.{column.name.lower()}",
                    )
        except Exception as exc:
            # Scope 构建遇到重复别名等异常时必须 fail-closed，不能因分析失败而默认放行。
            logger.warning("数据权限字段作用域解析失败")
            return referenced_columns, {
                "rule_id": "block_ambiguous_column",
                "reason": "无法安全解析字段作用域",
                "details": {"error_type": type(exc).__name__},
            }

        return referenced_columns, None

    def _stars_in_scope(self, scope: Scope) -> list[exp.Star]:
        """只返回当前 SELECT 的通配符，子查询通配符由子 scope 单独处理。"""
        return [
            star
            for star in scope.expression.find_all(exp.Star)
            if star.find_ancestor(exp.Select) is scope.expression
        ]

    def _resolve_scope_star(
        self,
        scope: Scope,
        star: exp.Star,
    ) -> tuple[str | None, bool]:
        """返回物理表名；第二个值表示该通配符来自已单独检查的派生 scope。"""
        parent = star.parent
        explicit_source = (
            (parent.table or "").lower()
            if isinstance(parent, exp.Column)
            else ""
        )
        selected_sources = scope.selected_sources

        if explicit_source:
            return self._physical_source(selected_sources.get(explicit_source))
        if len(selected_sources) == 1:
            return self._physical_source(next(iter(selected_sources.values())))
        return None, False

    def _resolve_scope_column(
        self,
        scope: Scope,
        column: exp.Column,
        schema_columns: dict[str, set[str]],
    ) -> tuple[str | None, bool]:
        """在当前 SELECT 的 source 集合内解析列，避免全局别名互相污染。"""
        selected_sources = scope.selected_sources
        explicit_source = (column.table or "").lower()
        if explicit_source:
            return self._physical_source(selected_sources.get(explicit_source))

        column_name = column.name.lower()
        matching_sources = [
            selected_source
            for selected_source in selected_sources.values()
            if self._source_exposes_column(selected_source, column_name, schema_columns)
        ]
        if len(matching_sources) == 1:
            return self._physical_source(matching_sources[0])
        if len(matching_sources) > 1:
            return None, False

        # 单一来源即使 Schema 不完整也可安全归属；多来源无命中时继续 fail-closed。
        if len(selected_sources) == 1:
            return self._physical_source(next(iter(selected_sources.values())))
        return None, False

    def _source_exposes_column(
        self,
        selected_source: tuple[exp.Expression, exp.Expression | Scope],
        column_name: str,
        schema_columns: dict[str, set[str]],
    ) -> bool:
        """判断 source 是否声明该列；派生 source 只查看它公开的投影名。"""
        _, source = selected_source
        if isinstance(source, exp.Table):
            table_name = (source.name or "").lower()
            return column_name in schema_columns.get(table_name, set())
        if isinstance(source, Scope):
            output_names = {
                str(name).lower()
                for name in source.expression.named_selects
                if name
            }
            return column_name in output_names or ALL_COLUMNS in output_names
        return False

    def _physical_source(
        self,
        selected_source: tuple[exp.Expression, exp.Expression | Scope] | None,
    ) -> tuple[str | None, bool]:
        """把 scope source 分类为物理表、派生查询或无法解析三种结果。"""
        if selected_source is None:
            return None, False
        _, source = selected_source
        if isinstance(source, exp.Table):
            table_name = (source.name or "").lower()
            return (table_name or None), False
        if isinstance(source, Scope):
            return None, True
        return None, False

    @staticmethod
    def _ambiguous_column_error(column_name: str) -> dict[str, Any]:
        return {
            "rule_id": "block_ambiguous_column",
            "reason": f"无法唯一判断字段归属: {column_name}",
            "details": {"column": column_name},
        }

    def _is_projection_alias_reference(self, column: exp.Column) -> bool:
        """ORDER/GROUP/HAVING 中的投影别名不是新的物理字段引用。"""
        if column.table:
            return False
        clause_types = (exp.Order, exp.Group, exp.Having, exp.Qualify)
        if not any(column.find_ancestor(clause_type) for clause_type in clause_types):
            return False
        select_scope = column.find_ancestor(exp.Select)
        if select_scope is None:
            return False
        aliases = {
            expression.alias.lower()
            for expression in select_scope.expressions
            if expression.alias
        }
        return column.name.lower() in aliases

    def _is_count_star(self, star: exp.Star) -> bool:
        """COUNT(*) 不暴露具体列，不能像 SELECT * 一样按字段泄露处理。"""
        parent = star.parent
        return isinstance(parent, exp.Count) or (
            isinstance(parent, exp.Anonymous) and str(parent.name).lower() == "count"
        )

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
