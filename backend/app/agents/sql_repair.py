# SQL 修复 Agent 模块
# 当 SQL 执行失败时，根据错误信息自动修复 SQL
# 是 LangGraph pipeline 中 SQL 执行失败后的重试节点

from typing import Dict, Any

from ..services.llm_service import llm_client
from ..models.schemas import SQLRepairOutput
from ..utils.schema_formatter import format_physical_schema
from ..utils.logger import logger
from ..utils.exceptions import SQLRepairError


class SQLRepairAgent:
    """SQL 修复 Agent，负责根据错误信息修复失败的 SQL"""

    async def repair(
        self,
        original_sql: str,
        error_message: str,
        schema_context: Dict[str, Any]
    ) -> SQLRepairOutput:
        """
        修复执行失败的 SQL

        Args:
            original_sql: 原始的有问题的 SQL
            error_message: 数据库返回的错误信息
            schema_context: 数据库 Schema 信息

        Returns:
            SQLRepairOutput: 包含 repaired_sql 和 repair_reason 的结构化结果

        Raises:
            SQLRepairError: LLM 调用失败或返回无效结果时抛出
        """
        # 将 Schema 字典格式化为 LLM 可读的文本
        schema_str = self._format_schema(schema_context)

        try:
            # 调用 LLM 修复 SQL，返回结构化 JSON
            result = await llm_client.repair_sql(original_sql, error_message, schema_str)

            # 构造标准化输出
            output = SQLRepairOutput(
                repaired_sql=result["repaired_sql"],
                repair_reason=result.get("repair_reason", "")
            )

            logger.info(f"SQL 修复成功: {output.repaired_sql[:100]}...")
            return output

        except (KeyError, TypeError) as e:
            # LLM 返回的 JSON 缺少必要字段
            logger.error(f"SQL 修复结果格式错误: {e}")
            raise SQLRepairError(f"SQL 修复结果格式错误: {e}")
        except Exception as e:
            logger.error(f"SQL 修复异常: {e}")
            raise SQLRepairError(f"SQL 修复失败: {e}")

    def _format_schema(self, schema_context: Dict[str, Any]) -> str:
        """将 Schema 字典格式化为 LLM 可读的物理表结构文本"""
        return format_physical_schema(schema_context)


# 全局 SQL 修复器实例
sql_repair_agent = SQLRepairAgent()
