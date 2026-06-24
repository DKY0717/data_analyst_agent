# Schema Grounding 模块
# 将意图解析的业务概念映射到物理 Schema 表达式，生成可解释的候选和路由。

from typing import Any

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

        # 收集所有需要的表和 JOIN 边
        all_tables: set[str] = set()
        all_joins: list[tuple[str, str]] = []
        for result in metric_results + dimension_results:
            for candidate in result.candidates:
                all_tables.update(candidate.tables)
            all_joins.extend(
                self._extract_join_edges(result)
            )

        route = self._build_route(all_tables, all_joins)

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
        tables = self._extract_tables_from_expression(metric["expression"])
        if default_table:
            tables.add(default_table)

        candidates.append(GroundingCandidate(
            candidate_id=metric.get("candidate_id", f"{concept}_default"),
            concept=concept,
            expression=metric["expression"],
            tables=sorted(tables),
            columns=self._extract_columns(metric["expression"]),
            score=1.0,
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
            override_tables = self._extract_tables_from_expression(override_expr)
            if default_table:
                override_tables.add(default_table)

            candidates.append(GroundingCandidate(
                candidate_id=override.get("candidate_id", f"{concept}_{dim_concept}")
                if isinstance(override, dict)
                else f"{concept}_{dim_concept}",
                concept=concept,
                expression=override_expr,
                tables=sorted(override_tables),
                columns=self._extract_columns(override_expr),
                score=0.9 if dim_used else 0.5,
                evidence=[f"按{dim_concept}维度拆分时使用"],
            ))

        return GroundingResult(concept=concept, candidates=candidates)

    def _ground_dimension(self, concept: str) -> GroundingResult:
        """将维度概念映射到语义层定义的字段。"""
        dimension = self.semantic.find_dimension(concept)
        if not dimension:
            return GroundingResult(concept=concept, candidates=[])

        fields = dimension.get("fields", [])
        required_joins = dimension.get("required_joins", [])

        tables: set[str] = set()
        for field in fields:
            tables.update(self._extract_tables_from_expression(field))
        for join in required_joins:
            tables.update(self._extract_tables_from_expression(join))

        candidates = [GroundingCandidate(
            candidate_id=dimension.get("candidate_id", concept),
            concept=concept,
            expression=", ".join(fields),
            tables=sorted(tables),
            columns=self._extract_columns(" ".join(fields)),
            score=1.0,
            evidence=[dimension.get("description", "")],
        )]

        return GroundingResult(concept=concept, candidates=candidates)

    def _build_route(
        self, tables: set[str], join_edges: list[tuple[str, str]]
    ) -> SchemaRoute:
        """构建覆盖所有表的最小 Schema 路由。"""
        # 去重 JOIN 边
        unique_edges = list(dict.fromkeys(join_edges))
        return SchemaRoute(
            selected_tables=sorted(tables),
            join_edges=unique_edges,
            confidence=1.0 if tables else 0.0,
        )

    def _extract_join_edges(self, result: GroundingResult) -> list[tuple[str, str]]:
        """从维度的 required_joins 提取 JOIN 边。"""
        edges = []
        for candidate in result.candidates:
            for evidence in candidate.evidence:
                if "=" in evidence and "." in evidence:
                    parts = evidence.split("=")
                    if len(parts) == 2:
                        left, right = parts[0].strip(), parts[1].strip()
                        if "." in left and "." in right:
                            edges.append((left, right))
        return edges

    @staticmethod
    def _extract_tables_from_expression(expression: str) -> set[str]:
        """从表达式中提取表名（table.column 格式的 table 部分）。"""
        tables: set[str] = set()
        for part in expression.replace(",", " ").split():
            if "." in part:
                table = part.split(".")[0].strip("()")
                if table and not table.startswith("'"):
                    tables.add(table)
        return tables

    @staticmethod
    def _extract_columns(expression: str) -> list[str]:
        """从表达式中提取列名（table.column 格式）。"""
        columns: list[str] = []
        for part in expression.replace(",", " ").split():
            part = part.strip("()")
            if "." in part and not part.startswith("'"):
                columns.append(part)
        return sorted(set(columns))


# 全局 Grounding 实例
schema_grounder = SchemaGrounder()
