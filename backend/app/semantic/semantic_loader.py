# 业务语义层加载器
# 将 YAML 中的业务指标和维度转换为 SQL Generator 可使用的上下文
# 通过 SEMANTIC_CONFIG_PATH 环境变量可切换不同领域的语义配置

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class SemanticLoader:
    """加载并查询业务语义配置（领域无关，通过 YAML 配置驱动）"""

    def __init__(self, config_path: str | Path | None = None):
        # 优先使用环境变量，其次使用参数，最后使用默认电商配置
        env_path = os.getenv("SEMANTIC_CONFIG_PATH", "")
        if env_path:
            self.config_path = Path(env_path)
        elif config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(__file__).parent / "ecommerce_metrics.yaml"
        self._data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """读取 YAML 配置；语义层是 SQL 生成的业务约束来源，因此缺失时应直接失败。"""
        with self.config_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """返回所有业务指标定义"""
        return self._data.get("metrics", {})

    def get_dimensions(self) -> Dict[str, Dict[str, Any]]:
        """返回所有业务维度定义"""
        return self._data.get("dimensions", {})

    def get_defaults(self) -> Dict[str, Any]:
        """返回默认时间字段、默认 LIMIT 和 SQL 方言"""
        return self._data.get("defaults", {})

    def find_metric(self, keyword: str) -> Optional[Dict[str, Any]]:
        """按指标 key、中文名称或别名查找指标"""
        return self._find_by_keyword(self.get_metrics(), keyword)

    def find_dimension(self, keyword: str) -> Optional[Dict[str, Any]]:
        """按维度 key、中文名称或别名查找维度"""
        return self._find_by_keyword(self.get_dimensions(), keyword)

    def _find_by_keyword(self, items: Dict[str, Dict[str, Any]], keyword: str) -> Optional[Dict[str, Any]]:
        """统一查找逻辑，返回时补充 key，方便调用方知道命中的配置项"""
        normalized_keyword = keyword.lower()
        for key, value in items.items():
            candidates = [key, value.get("name", ""), *value.get("aliases", [])]
            if any(str(candidate).lower() == normalized_keyword for candidate in candidates):
                return {"key": key, **value}
        return None

    def format_for_prompt(self) -> str:
        """格式化为 LLM 可读摘要，拼接到物理 Schema 后面"""
        lines: list[str] = []

        lines.append("业务指标:")
        for metric_key, metric in self.get_metrics().items():
            # 稳定英文 key 同时作为结果列契约，避免模型按中文问题自由生成中文别名。
            lines.append(f"- {metric['name']} = {metric['expression']}")
            lines.append(f"  输出别名: {metric_key}")
            if metric.get("required_joins"):
                lines.append(f"  需要 JOIN: {'; '.join(metric['required_joins'])}")
            for dimension_key, expression in metric.get(
                "dimension_overrides", {}
            ).items():
                dimension = self.get_dimensions().get(dimension_key, {})
                dimension_name = dimension.get("name", dimension_key)
                # v0.6 覆盖项升级为结构化候选；兼容旧字符串配置便于平滑迁移。
                override_expression = (
                    expression.get("expression")
                    if isinstance(expression, dict)
                    else expression
                )
                lines.append(f"  按{dimension_name}时使用: {override_expression}")
            lines.append(f"  说明: {metric.get('description', '')}")

        lines.append("")
        lines.append("业务维度:")
        for dimension in self.get_dimensions().values():
            lines.append(f"- {dimension['name']}: {', '.join(dimension.get('fields', []))}")
            if dimension.get("required_joins"):
                lines.append(f"  需要 JOIN: {'; '.join(dimension['required_joins'])}")
            lines.append(f"  说明: {dimension.get('description', '')}")

        defaults = self.get_defaults()
        lines.append("")
        lines.append("默认规则:")
        lines.append(f"- 默认时间字段: {defaults.get('time_field')}")
        lines.append(f"- 默认返回上限: {defaults.get('limit')}")
        lines.append(f"- SQL 方言: {defaults.get('dialect')}")

        return "\n".join(lines)


# 全局语义层加载器，供 SQL Generator 复用
semantic_loader = SemanticLoader()
