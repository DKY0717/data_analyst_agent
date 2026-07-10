# SQL 优化建议模块
# 负责把已执行成功的 SQL 转换成可解释的优化建议，补齐 API 中 optimization_suggestions 字段

from typing import Any, Dict, List

import sqlglot
from sqlglot import exp

from ..config import settings
from ..db.query_runner import query_runner
from ..security.sql_guard import sql_guard
from ..utils.logger import logger


class SQLOptimizer:
    """轻量 SQL 优化器：基于 AST、查询结果和 DuckDB EXPLAIN 生成规则化建议"""

    def __init__(
        self,
        max_rows: int = None,
        query_runner_service=None,
        sql_guard_service=None,
    ):
        self.max_rows = max_rows or settings.SQL_MAX_ROWS
        self._query_runner = query_runner_service
        self._sql_guard = sql_guard_service

    def optimize(self, sql: str, query_result: Dict[str, Any]) -> List[str]:
        """生成 SQL 优化建议

        Args:
            sql: 已通过 SQL Guard 的安全 SQL
            query_result: QueryRunner.execute() 返回的执行结果

        Returns:
            优化建议列表；没有明显问题时返回空列表
        """
        suggestions: List[str] = []

        # 执行失败时不分析优化，避免把错误 SQL 当成可优化查询继续执行 EXPLAIN。
        if not query_result.get("success"):
            return suggestions

        suggestions.extend(self._suggest_from_sql_shape(sql))
        suggestions.extend(self._suggest_from_result_size(query_result))

        # 只有当 AST 和结果规模都没发现优化点时，才执行 EXPLAIN（额外数据库调用）。
        if not suggestions:
            plan_text = self._load_explain_plan(sql)
            suggestions.extend(self._suggest_from_plan(plan_text))

        return self._deduplicate(suggestions)

    def _suggest_from_sql_shape(self, sql: str) -> List[str]:
        """从 SQL 结构本身识别可解释的优化点"""
        suggestions: List[str] = []

        try:
            parsed = sqlglot.parse_one(sql, dialect="duckdb")
        except Exception as e:
            logger.warning(f"SQL 优化器解析 SQL 失败: {e}")
            return suggestions

        # SELECT * 会放大扫描和网络传输成本，是面试中最容易讲清楚的优化点之一。
        if any(isinstance(expression, exp.Star) for expression in parsed.find_all(exp.Star)):
            suggestions.append("避免使用 SELECT *，只选择分析需要的字段，减少列扫描和结果传输成本。")

        return suggestions

    def _suggest_from_result_size(self, query_result: Dict[str, Any]) -> List[str]:
        """从结果规模判断用户是否需要补充过滤条件"""
        row_count = query_result.get("row_count", len(query_result.get("rows", [])))

        if row_count >= self.max_rows:
            return ["结果达到返回上限，建议增加 WHERE 条件、时间范围或分页，避免一次性返回过多数据。"]

        return []

    def _load_explain_plan(self, sql: str) -> str:
        """通过 SQL Guard 校验后的 EXPLAIN 获取 DuckDB 执行计划"""
        explain_sql = f"EXPLAIN {sql}"
        guard_service = self._sql_guard or sql_guard
        runner_service = self._query_runner or query_runner
        guard_result = guard_service.validate(explain_sql)
        if not guard_result["is_safe"]:
            logger.warning(f"EXPLAIN SQL 未通过安全校验: {guard_result['reason']}")
            return ""

        # EXPLAIN 也走 QueryRunner，统一复用执行错误捕获和结构化返回格式。
        result = runner_service.execute(guard_result["sanitized_sql"])
        if not result.get("success"):
            logger.warning(f"EXPLAIN 执行失败: {result.get('error')}")
            return ""

        return "\n".join(str(cell) for row in result.get("rows", []) for cell in row)

    def _suggest_from_plan(self, plan_text: str) -> List[str]:
        """从 DuckDB 执行计划文本中提取简单但可讲清楚的建议"""
        if not plan_text:
            return []

        normalized_plan = plan_text.upper()
        if "SEQ_SCAN" in normalized_plan:
            return ["执行计划包含顺序扫描，建议优先检查是否可以增加筛选条件或先聚合再排序。"]

        return []

    def _deduplicate(self, suggestions: List[str]) -> List[str]:
        """保持输出顺序去重，避免多个规则产生重复提示"""
        deduplicated: List[str] = []
        for suggestion in suggestions:
            if suggestion not in deduplicated:
                deduplicated.append(suggestion)
        return deduplicated


# 全局 SQL 优化器实例，供 LangGraph 节点复用
sql_optimizer = SQLOptimizer()
