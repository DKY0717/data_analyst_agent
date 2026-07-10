# Schema Grounding 模块
# 将意图解析的业务概念映射到物理 Schema 表达式，生成可解释的候选和路由。

from collections import deque
from itertools import combinations
from typing import Any

import sqlglot
from sqlglot import exp

from ..analysis_intent.models import (
    AnalysisIntent,
    GroundingCandidate,
    GroundingResult,
    SchemaRoute,
)
from ..semantic.semantic_loader import SemanticLoader, semantic_loader


class SchemaGrounder:
    """将业务概念映射到物理 Schema，保留全部候选和 JOIN 路径。"""

    def __init__(self, semantic: SemanticLoader | None = None):
        self.semantic = semantic or semantic_loader

    def ground(self, intent: AnalysisIntent) -> dict[str, Any]:
        """对意图中的每个指标和维度执行 Grounding，返回结构化结果。"""
        metric_results = [
            self._ground_metric(slot.concept, intent)
            for slot in intent.metrics
        ]
        dimension_results = [
            self._ground_dimension(slot.concept)
            for slot in intent.dimensions
        ]

        # 路由只采用当前上下文中得分最高的候选，避免未命中的覆盖候选污染表集合。
        all_tables: set[str] = set()
        for result in metric_results + dimension_results:
            if result.candidates:
                selected = max(result.candidates, key=lambda candidate: candidate.score)
                all_tables.update(selected.tables)

        route = self._build_route(all_tables)

        return {
            "metric_groundings": [r.model_dump() for r in metric_results],
            "dimension_groundings": [r.model_dump() for r in dimension_results],
            "schema_route": route.model_dump(),
        }

    def _ground_metric(self, concept: str, intent: AnalysisIntent) -> GroundingResult:
        """将指标概念映射到语义层定义的表达式。"""
        metric = self.semantic.find_metric(concept)
        if not metric:
            return GroundingResult(concept=concept, candidates=[])

        candidates = []
        # 主候选：默认表达式
        default_table = metric.get("default_table", "")
        tables = self._source_tables(metric, metric["expression"])
        if default_table:
            tables.add(default_table)

        active_overrides = {
            dimension.concept
            for dimension in intent.dimensions
            if dimension.concept in metric.get("dimension_overrides", {})
        }

        candidates.append(GroundingCandidate(
            candidate_id=metric.get("candidate_id", f"{concept}_default"),
            concept=concept,
            expression=metric["expression"],
            tables=sorted(tables),
            columns=self._source_columns(metric, metric["expression"], tables),
            score=0.8 if active_overrides else 1.0,
            evidence=[metric.get("description", "")],
        ))

        # 维度覆盖候选：按特定维度拆分时使用不同表达式
        for dim_concept, override in metric.get("dimension_overrides", {}).items():
            override_expr = (
                override.get("expression", "")
                if isinstance(override, dict)
                else str(override)
            )
            if not override_expr:
                continue
            # 检查当前意图是否使用了该维度
            dim_used = any(d.concept == dim_concept for d in intent.dimensions)
            override_config = override if isinstance(override, dict) else {}
            override_tables = self._source_tables(override_config, override_expr)
            if default_table and not override_config.get("source_tables"):
                override_tables.add(default_table)

            candidates.append(GroundingCandidate(
                candidate_id=override.get("candidate_id", f"{concept}_{dim_concept}")
                if isinstance(override, dict)
                else f"{concept}_{dim_concept}",
                concept=concept,
                expression=override_expr,
                tables=sorted(override_tables),
                columns=self._source_columns(
                    override_config,
                    override_expr,
                    override_tables,
                ),
                score=1.0 if dim_used else 0.5,
                evidence=[f"按{dim_concept}维度拆分时使用"],
            ))

        return GroundingResult(concept=concept, candidates=candidates)

    def _ground_dimension(self, concept: str) -> GroundingResult:
        """将维度概念映射到语义层定义的字段。"""
        dimension = self.semantic.find_dimension(concept)
        if not dimension:
            return GroundingResult(concept=concept, candidates=[])

        fields = dimension.get("fields", [])
        tables = set(dimension.get("source_tables") or [])
        if not tables:
            for field in fields:
                tables.update(self._extract_tables_from_expression(field))

        candidates = [GroundingCandidate(
            candidate_id=dimension.get("candidate_id", concept),
            concept=concept,
            expression=", ".join(fields),
            tables=sorted(tables),
            columns=self._extract_columns(", ".join(fields), tables),
            score=1.0,
            evidence=[dimension.get("description", "")],
        )]

        return GroundingResult(concept=concept, candidates=candidates)

    def _build_route(self, tables: set[str]) -> SchemaRoute:
        """使用全局 JOIN 图构建覆盖候选表的最小连接子图。"""
        configured_edges = self._configured_join_edges()
        used_edges: set[tuple[str, str]] = set()
        connected = True

        # 电商 JOIN 图是树状结构；所有终端表两两最短路径的并集就是最小连接子图。
        for left_table, right_table in combinations(sorted(tables), 2):
            path = self._shortest_path(left_table, right_table, configured_edges)
            if path is None:
                connected = False
                continue
            used_edges.update(path)

        selected_tables = set(tables)
        ordered_edges = [edge for edge in configured_edges if edge in used_edges]
        for left_column, right_column in ordered_edges:
            selected_tables.add(self._table_name(left_column))
            selected_tables.add(self._table_name(right_column))

        return SchemaRoute(
            selected_tables=sorted(selected_tables),
            join_edges=ordered_edges,
            evidence={
                "semantic_join_graph": [
                    f"{left} = {right}" for left, right in ordered_edges
                ]
            } if ordered_edges else {},
            confidence=1.0 if tables and connected else 0.0,
        )

    def _configured_join_edges(self) -> list[tuple[str, str]]:
        """把 YAML JOIN 图规范化为稳定的全限定字段边。"""
        edges: list[tuple[str, str]] = []
        for item in self.semantic.get_joins():
            if not isinstance(item, dict):
                continue
            left = str(item.get("left") or "").strip().lower()
            right = str(item.get("right") or "").strip().lower()
            if self._is_qualified_column(left) and self._is_qualified_column(right):
                edges.append((left, right))
        return list(dict.fromkeys(edges))

    def _shortest_path(
        self,
        start: str,
        target: str,
        edges: list[tuple[str, str]],
    ) -> list[tuple[str, str]] | None:
        """在表级 JOIN 图中查找最短路径，同时保留字段级边。"""
        if start == target:
            return []

        adjacency: dict[str, list[tuple[str, tuple[str, str]]]] = {}
        for edge in edges:
            left_table = self._table_name(edge[0])
            right_table = self._table_name(edge[1])
            adjacency.setdefault(left_table, []).append((right_table, edge))
            adjacency.setdefault(right_table, []).append((left_table, edge))

        queue = deque([(start, [])])
        visited = {start}
        while queue:
            table, path = queue.popleft()
            for neighbor, edge in adjacency.get(table, []):
                if neighbor in visited:
                    continue
                next_path = [*path, edge]
                if neighbor == target:
                    return next_path
                visited.add(neighbor)
                queue.append((neighbor, next_path))
        return None

    def _source_tables(self, config: dict[str, Any], expression: str) -> set[str]:
        """优先使用语义层显式物理表，缺失时才从 AST 安全推导。"""
        configured = {
            str(table).strip().lower()
            for table in config.get("source_tables", [])
            if str(table).strip()
        }
        return configured or self._extract_tables_from_expression(expression)

    def _source_columns(
        self,
        config: dict[str, Any],
        expression: str,
        tables: set[str],
    ) -> list[str]:
        configured = [
            str(column).strip().lower()
            for column in config.get("source_columns", [])
            if self._is_qualified_column(str(column).strip())
        ]
        return sorted(set(configured)) or self._extract_columns(expression, tables)

    @staticmethod
    def _extract_tables_from_expression(expression: str) -> set[str]:
        """通过 SQL AST 提取全限定字段中的表名，解析失败时不猜测。"""
        try:
            parsed = sqlglot.parse_one(f"SELECT {expression}", dialect="duckdb")
        except Exception:
            return set()
        return {
            column.table.lower()
            for column in parsed.find_all(exp.Column)
            if column.table
        }

    @staticmethod
    def _extract_columns(expression: str, allowed_tables: set[str] | None = None) -> list[str]:
        """通过 SQL AST 提取规范化全限定字段，并过滤派生别名。"""
        try:
            parsed = sqlglot.parse_one(f"SELECT {expression}", dialect="duckdb")
        except Exception:
            return []

        normalized = []
        for column in parsed.find_all(exp.Column):
            table = (column.table or "").lower()
            if not table or (allowed_tables is not None and table not in allowed_tables):
                continue
            normalized.append(f"{table}.{column.name.lower()}")
        return sorted(set(normalized))

    @staticmethod
    def _is_qualified_column(value: str) -> bool:
        parts = value.split(".")
        return len(parts) == 2 and all(part.strip() for part in parts)

    @staticmethod
    def _table_name(column: str) -> str:
        return column.split(".", 1)[0].lower()


# 全局 Grounding 实例
schema_grounder = SchemaGrounder()
