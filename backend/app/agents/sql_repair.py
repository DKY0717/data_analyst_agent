# SQL 修复 Agent 模块（增强版）
# 当 SQL 执行失败时，根据错误分类采用差异化修复策略

from typing import Dict, Any

from ..services.llm_service import llm_client
from ..models.schemas import SQLRepairOutput
from ..utils.schema_formatter import format_physical_schema
from ..utils.logger import logger
from ..services.tracing import build_sql_metadata
from ..utils.exceptions import SQLRepairError
from ..security.error_classifier import classify_sql_error, SQLErrorCategory


# 不同错误类别的修复 prompt 策略
_REPAIR_STRATEGIES = {
    SQLErrorCategory.COLUMN_NOT_FOUND: {
        "system_suffix": """
重点修复策略：
1. 仔细对照 Schema 中的列名，找到最可能匹配的正确列名
2. 如果是中文别名问题，使用 Schema 中的物理列名
3. 如果是多表 JOIN 后列名歧义，加表别名前缀
4. 不要改变查询意图，只修正列名""",
        "temperature": 0.05,  # 列名修正需要高确定性
    },
    SQLErrorCategory.TABLE_NOT_FOUND: {
        "system_suffix": """
重点修复策略：
1. 对照 Schema 中的表名列表，找到正确的表名
2. 检查是否需要 JOIN 来获取所需数据
3. 不要创建新表，只使用已有表""",
        "temperature": 0.05,
    },
    SQLErrorCategory.FUNCTION_NOT_FOUND: {
        "system_suffix": """
重点修复策略：
1. 将不存在的函数替换为 DuckDB 支持的等效函数
2. 常见替换：DATE_FORMAT→STRFTIME，IFNULL→COALESCE，NOW()→CURRENT_TIMESTAMP
3. 季度提取用 EXTRACT(QUARTER FROM date_column)
4. strftime 返回字符串，参与算术前必须 CAST""",
        "temperature": 0.1,
    },
    SQLErrorCategory.TYPE_MISMATCH: {
        "system_suffix": """
重点修复策略：
1. 字符串转数值：CAST(column AS INTEGER) 或 CAST(column AS DECIMAL(10,2))
2. 日期格式：确保比较双方都是 DATE/TIMESTAMP 类型
3. COALESCE 的两个参数类型必须一致
4. 不要改变查询意图""",
        "temperature": 0.1,
    },
    SQLErrorCategory.AGGREGATE_MISUSE: {
        "system_suffix": """
重点修复策略：
1. SELECT 中的非聚合列必须出现在 GROUP BY 中
2. 或者将非聚合列改为聚合函数（MAX、MIN、FIRST）
3. 如果需要按时间分组，用 DATE_TRUNC 而非原始日期列""",
        "temperature": 0.1,
    },
    SQLErrorCategory.SYNTAX: {
        "system_suffix": """
重点修复策略：
1. 检查括号是否匹配、逗号是否遗漏
2. DuckDB 不支持 LIMIT offset, count，用 LIMIT count OFFSET offset
3. CTE (WITH 子句) 后面直接跟 SELECT，不需要分号
4. 字符串用单引号，列名用双引号或不加引号""",
        "temperature": 0.1,
    },
    SQLErrorCategory.AMBIGUOUS_COLUMN: {
        "system_suffix": """
重点修复策略：
1. 给所有 JOIN 表加别名
2. SELECT 和 WHERE 中的列名都加表别名前缀
3. 如：o.order_id, c.customer_name""",
        "temperature": 0.05,
    },
    SQLErrorCategory.TIMEOUT: {
        "system_suffix": """
重点修复策略：
1. 添加更精确的 WHERE 条件缩小扫描范围
2. 减少 JOIN 表数量
3. 如果是全表聚合，考虑是否需要加时间过滤
4. 避免 SELECT *，只选需要的列""",
        "temperature": 0.1,
    },
}

# 默认策略（未知错误）
_DEFAULT_STRATEGY = {
    "system_suffix": """
请仔细分析错误信息，修正 SQL 中的问题。不要改变查询意图。""",
    "temperature": 0.1,
}


class SQLRepairAgent:
    """SQL 修复 Agent，根据错误分类采用差异化修复策略"""

    async def repair(
        self,
        original_sql: str,
        error_message: str,
        schema_context: Dict[str, Any],
        error_type: str = "",
    ) -> SQLRepairOutput:
        """
        修复执行失败的 SQL

        Args:
            original_sql: 原始的有问题的 SQL
            error_message: 数据库返回的错误信息
            schema_context: 数据库 Schema 信息
            error_type: Python 异常类型名

        Returns:
            SQLRepairOutput: 包含 repaired_sql 和 repair_reason 的结构化结果
        """
        schema_str = self._format_schema(schema_context)

        # 1. 错误分类
        classified = classify_sql_error(error_message, error_type)
        logger.info("SQL 错误分类: %s", classified.category.value)

        # 2. 选择修复策略
        strategy = _REPAIR_STRATEGIES.get(classified.category, _DEFAULT_STRATEGY)

        # 3. 构建修复 prompt
        repair_reason = f"[{classified.category.value}] {classified.repair_hint}"

        try:
            result = await llm_client.repair_sql(
                original_sql=original_sql,
                error_message=error_message,
                schema_info=schema_str,
                system_suffix=strategy["system_suffix"],
                temperature=strategy["temperature"],
            )

            output = SQLRepairOutput(
                repaired_sql=result["repaired_sql"],
                repair_reason=repair_reason,
            )

            metadata = build_sql_metadata(output.repaired_sql)
            logger.info(
                "SQL 修复成功 (%s): hash=%s type=%s tables=%s",
                classified.category.value,
                metadata["hash"],
                metadata["statement_type"],
                metadata["tables"],
            )
            return output

        except (KeyError, TypeError) as e:
            logger.error("SQL 修复结果格式错误: %s", type(e).__name__)
            raise SQLRepairError("SQL 修复结果格式错误") from e
        except Exception as e:
            logger.error("SQL 修复异常: %s", type(e).__name__)
            raise SQLRepairError("SQL 修复失败") from e

    def _format_schema(self, schema_context: Dict[str, Any]) -> str:
        return format_physical_schema(schema_context)


sql_repair_agent = SQLRepairAgent()
