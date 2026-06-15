"""合并物理 Schema、业务语义和 Join 图的统一元数据目录。"""

from copy import deepcopy
from typing import Any

from ..db.schema_loader import schema_loader
from ..semantic.semantic_loader import semantic_loader


class MetadataCatalog:
    """为意图解析、Grounding 和图路由提供同一份稳定元数据视图。"""

    def __init__(
        self,
        tables: dict[str, dict[str, Any]],
        metrics: dict[str, dict[str, Any]],
        dimensions: dict[str, dict[str, Any]],
    ):
        # Catalog 持有独立副本，避免调用方修改 Schema Loader 或语义层的共享状态。
        self.tables = deepcopy(tables)
        self.metrics = deepcopy(metrics)
        self.dimensions = deepcopy(dimensions)
        self.join_edges = self._build_join_edges()

    @classmethod
    def from_sources(
        cls,
        schema: dict[str, Any] | None = None,
        semantic=None,
    ) -> "MetadataCatalog":
        """从可注入来源构建目录，生产复用全局加载器，测试可传隔离数据。"""
        physical_schema = schema if schema is not None else schema_loader.get_full_schema()
        semantic_source = semantic or semantic_loader
        return cls(
            tables=physical_schema.get("tables", {}),
            metrics=semantic_source.get_metrics(),
            dimensions=semantic_source.get_dimensions(),
        )

    def find_metric_candidates(self, concept: str) -> list[dict[str, Any]]:
        """按稳定 key、名称或别名召回指标候选。"""
        return self._find_candidates(self.metrics, concept)

    def find_dimension_candidates(self, concept: str) -> list[dict[str, Any]]:
        """按稳定 key、名称或别名召回维度候选。"""
        return self._find_candidates(self.dimensions, concept)

    def table_schema(self, table_name: str) -> dict[str, Any]:
        """返回隔离副本，防止 Context Builder 裁剪时污染完整目录。"""
        return deepcopy(self.tables.get(table_name, {}))

    def _build_join_edges(self) -> list[tuple[str, str]]:
        """将每个外键规范化为本地列到引用列的稳定有向边。"""
        edges = []
        for table_name, table in self.tables.items():
            for foreign_key in table.get("foreign_keys", []):
                edges.append(
                    (
                        f"{table_name}.{foreign_key['column']}",
                        (
                            f"{foreign_key['referenced_table']}."
                            f"{foreign_key['referenced_column']}"
                        ),
                    )
                )
        return sorted(set(edges))

    @staticmethod
    def _find_candidates(
        items: dict[str, dict[str, Any]], concept: str
    ) -> list[dict[str, Any]]:
        normalized = str(concept).strip().casefold()
        matches = []
        for key, value in items.items():
            names = [key, value.get("name", ""), *value.get("aliases", [])]
            if any(str(name).strip().casefold() == normalized for name in names):
                matches.append({"key": key, **deepcopy(value)})
        return sorted(matches, key=lambda item: item["key"])
