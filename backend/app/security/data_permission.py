# 数据权限 Guard
# 在 SQL Guard 确认语句安全后，继续检查“这个用户能不能看这些表和字段”。

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

from ..agents.audit import audit_report_builder
from ..utils.logger import logger


ALL_COLUMNS = "*"


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


# 第一版采用内置 RBAC 策略，让项目不依赖外部 IAM 也能展示企业数据治理闭环。
ROLE_POLICIES: dict[str, dict[str, set[str]]] = {
    "admin": {
        ALL_COLUMNS: {ALL_COLUMNS},
    },
    "analyst": {
        "regions": {ALL_COLUMNS},
        "customers": {"customer_id", "gender", "age", "region_id", "register_date"},
        "categories": {ALL_COLUMNS},
        "products": {ALL_COLUMNS},
        "orders": {ALL_COLUMNS},
        "order_items": {ALL_COLUMNS},
        "payments": {"payment_id", "order_id", "payment_method", "payment_status", "paid_at"},
        "refunds": {"refund_id", "order_id", "refund_reason", "refund_date"},
    },
    "support": {
        "regions": {ALL_COLUMNS},
        "categories": {ALL_COLUMNS},
        "products": {ALL_COLUMNS},
        "orders": {ALL_COLUMNS},
        "order_items": {ALL_COLUMNS},
    },
}


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

        allowed_tables = self._allowed_tables(permission_user.roles)
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
            allowed_columns = allowed_tables.get(table) or allowed_tables.get(ALL_COLUMNS)
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

        return self._allowed(permission_user, referenced_tables, referenced_columns)

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

    def _allowed_tables(self, roles: list[str]) -> dict[str, set[str]]:
        """多个角色取权限并集；未知角色不授予任何隐式权限。"""
        allowed: dict[str, set[str]] = {}
        for role in roles:
            for table, columns in ROLE_POLICIES.get(role, {}).items():
                allowed.setdefault(table, set()).update(columns)
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

    def _allowed(
        self,
        user: PermissionUser,
        referenced_tables: list[str],
        referenced_columns: list[str],
    ) -> DataPermissionResult:
        return DataPermissionResult(
            is_allowed=True,
            reason="SQL 通过数据权限检查",
            blocked_rule=None,
            audit_events=[
                self._event("success", "SQL 通过数据权限检查", user, referenced_tables, referenced_columns)
            ],
            referenced_tables=referenced_tables,
            referenced_columns=referenced_columns,
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
    ) -> dict[str, Any]:
        """审计事件只记录决策证据，不泄露完整策略或凭证。"""
        event_details = {
            "user_id": user.user_id,
            "auth_method": user.auth_method,
            "roles": user.roles,
            "tables": referenced_tables,
            "columns_checked": referenced_columns,
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
