# 数据权限策略加载器
# 将表、字段、行级权限从代码迁移到可审计的 YAML 配置。

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlglot
import yaml
from sqlglot import exp

from ..config import settings

ALL_COLUMNS = "*"


class PermissionPolicyError(ValueError):
    """策略文件缺失、格式错误或语义不安全时抛出。"""


@dataclass(frozen=True)
class RowFilterPolicy:
    expression: str
    rule_id: str
    referenced_tables: set[str]
    referenced_columns: set[str]


@dataclass(frozen=True)
class TablePolicy:
    columns: set[str]
    row_filter: RowFilterPolicy | None = None


@dataclass(frozen=True)
class RolePolicy:
    tables: dict[str, TablePolicy]


@dataclass(frozen=True)
class PermissionPolicy:
    version: int
    roles: dict[str, RolePolicy]


def default_policy_path() -> Path:
    return Path(__file__).resolve().parent / "data_permissions.yaml"


def configured_policy_path() -> Path:
    raw_path = os.getenv("DATA_PERMISSION_POLICY_PATH") or settings.DATA_PERMISSION_POLICY_PATH
    if raw_path:
        path = Path(raw_path)
        return path if path.is_absolute() else settings.BASE_DIR / path
    return default_policy_path()


class PermissionPolicyLoader:
    """加载并校验数据权限策略。"""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else configured_policy_path()

    def load(self) -> PermissionPolicy:
        if not self.path.exists():
            raise PermissionPolicyError(f"Permission policy file not found: {self.path}")

        try:
            with self.path.open("r", encoding="utf-8") as file:
                raw = yaml.safe_load(file)
        except yaml.YAMLError as exc:
            raise PermissionPolicyError("Permission policy YAML is malformed") from exc

        if not isinstance(raw, dict):
            raise PermissionPolicyError("Permission policy must be a mapping")
        version = raw.get("version")
        if version != 1:
            raise PermissionPolicyError("Permission policy version must be 1")

        roles_raw = raw.get("roles")
        if not isinstance(roles_raw, dict) or not roles_raw:
            raise PermissionPolicyError("Permission policy roles must be a non-empty mapping")

        roles = {
            self._normalize_name(role_name, "role"): self._parse_role(role_name, role_config)
            for role_name, role_config in roles_raw.items()
        }
        return PermissionPolicy(version=version, roles=roles)

    def _parse_role(self, role_name: Any, role_config: Any) -> RolePolicy:
        if not isinstance(role_config, dict):
            raise PermissionPolicyError(f"Role policy must be a mapping: {role_name}")
        tables_raw = role_config.get("tables")
        if not isinstance(tables_raw, dict) or not tables_raw:
            raise PermissionPolicyError(f"Role tables must be a non-empty mapping: {role_name}")

        tables = {
            self._normalize_table_name(table_name): self._parse_table(
                role_name,
                table_name,
                table_config,
            )
            for table_name, table_config in tables_raw.items()
        }
        return RolePolicy(tables=tables)

    def _parse_table(self, role_name: Any, table_name: Any, table_config: Any) -> TablePolicy:
        if not isinstance(table_config, dict):
            raise PermissionPolicyError(f"Table policy must be a mapping: {role_name}.{table_name}")

        columns_raw = table_config.get("columns")
        if not isinstance(columns_raw, list) or not columns_raw:
            raise PermissionPolicyError(f"Table columns must be a non-empty list: {role_name}.{table_name}")
        columns = {self._normalize_column_name(column) for column in columns_raw}

        row_filter = None
        if "row_filter" in table_config:
            row_filter = self._parse_row_filter(role_name, table_name, table_config["row_filter"])

        return TablePolicy(columns=columns, row_filter=row_filter)

    def _parse_row_filter(self, role_name: Any, table_name: Any, row_filter_raw: Any) -> RowFilterPolicy:
        if not isinstance(row_filter_raw, dict):
            raise PermissionPolicyError(f"row filter must be a mapping: {role_name}.{table_name}")
        expression = str(row_filter_raw.get("expression") or "").strip()
        rule_id = str(row_filter_raw.get("rule_id") or "").strip()
        if not expression:
            raise PermissionPolicyError(f"row filter expression is required: {role_name}.{table_name}")
        if not rule_id:
            raise PermissionPolicyError(f"row filter rule_id is required: {role_name}.{table_name}")

        try:
            parsed = sqlglot.parse_one(expression, dialect="duckdb", into=exp.Condition)
        except Exception as exc:
            raise PermissionPolicyError(f"row filter expression is invalid: {role_name}.{table_name}") from exc

        for subquery in parsed.find_all(exp.Subquery):
            if not isinstance(subquery.this, exp.Select):
                raise PermissionPolicyError(f"row filter subquery must be SELECT-only: {role_name}.{table_name}")

        referenced_tables = {
            table.name.lower()
            for table in parsed.find_all(exp.Table)
            if table.name
        }
        referenced_columns = {
            column.name.lower()
            for column in parsed.find_all(exp.Column)
            if column.name
        }

        return RowFilterPolicy(
            expression=expression,
            rule_id=rule_id,
            referenced_tables=referenced_tables,
            referenced_columns=referenced_columns,
        )

    def _normalize_table_name(self, value: Any) -> str:
        if str(value).strip() == ALL_COLUMNS:
            return ALL_COLUMNS
        return self._normalize_name(value, "table")

    def _normalize_column_name(self, value: Any) -> str:
        if str(value).strip() == ALL_COLUMNS:
            return ALL_COLUMNS
        return self._normalize_name(value, "column")

    @staticmethod
    def _normalize_name(value: Any, kind: str) -> str:
        name = str(value or "").strip().lower()
        if not name:
            raise PermissionPolicyError(f"Permission policy {kind} name cannot be empty")
        return name
