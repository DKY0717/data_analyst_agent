# SQL 生成 Agent 模块
# 将用户的自然语言问题转换为可执行的 SQL 查询
# 是 LangGraph pipeline 中的第一个节点

import sqlglot
from typing import Dict, Any

from ..services.llm_service import llm_client
from ..models.schemas import SQLGeneratorOutput
from ..semantic.semantic_loader import semantic_loader
from ..utils.logger import logger
from ..utils.exceptions import LLMError


class SQLGenerator:
    """SQL 生成 Agent，负责自然语言 → SQL 的转换"""

    async def generate(
        self,
        question: str,
        schema_context: Dict[str, Any],
        conversation_context: str = "",
    ) -> SQLGeneratorOutput:
        """
        根据自然语言问题和数据库 Schema 生成 SQL

        Args:
            question: 用户的自然语言问题
            schema_context: 数据库 Schema 信息，来自 SchemaLoader.get_full_schema()
            conversation_context: 多轮追问上下文摘要；为空时按单轮查询处理

        Returns:
            SQLGeneratorOutput: 包含 sql、tables、columns、explanation 的结构化结果

        Raises:
            LLMError: LLM 调用失败或返回无效结果时抛出
        """
        # 将 Schema 字典格式化为 LLM 可读的文本
        schema_str = self._format_schema(schema_context)

        try:
            # 调用 LLM 生成 SQL，返回结构化 JSON
            result = await llm_client.generate_sql(question, schema_str, conversation_context)

            # 从生成的 SQL 中提取使用的列名（LLM 返回的 tables 不含 columns）
            columns = self._extract_columns(result.get("sql", ""))

            # 构造标准化输出
            output = SQLGeneratorOutput(
                sql=result["sql"],
                tables=result.get("tables", []),
                columns=columns,
                explanation=result.get("explanation", "")
            )

            logger.info(f"SQL 生成成功: {output.sql[:100]}...")
            return output

        except (KeyError, TypeError) as e:
            # LLM 返回的 JSON 缺少必要字段
            logger.error(f"SQL 生成结果格式错误: {e}")
            raise LLMError(f"SQL 生成结果格式错误: {e}")
        except LLMError:
            # LLM 调用本身失败，直接向上抛
            raise
        except Exception as e:
            logger.error(f"SQL 生成异常: {e}")
            raise LLMError(f"SQL 生成失败: {e}")

    def _format_schema(self, schema_context: Dict[str, Any]) -> str:
        """
        将 Schema 字典格式化为 LLM 可读的文本

        输入格式示例:
        {
            "tables": {
                "orders": {
                    "table_name": "orders",
                    "columns": [{"name": "id", "type": "INTEGER", "nullable": False}, ...],
                    "primary_keys": ["id"]
                }
            }
        }

        输出格式:
        表名: orders
          主键: id
          字段:
            - id (INTEGER, NOT NULL)
            - customer_id (INTEGER, NULLABLE)
        """
        tables = schema_context.get("tables", {})
        lines = []

        for table_name, table_info in tables.items():
            lines.append(f"表名: {table_name}")

            # 标注主键，帮助 LLM 理解表间关系
            primary_keys = table_info.get("primary_keys", [])
            if primary_keys:
                lines.append(f"  主键: {', '.join(primary_keys)}")

            # 列出所有字段及其类型和可空性
            columns = table_info.get("columns", [])
            lines.append("  字段:")
            for col in columns:
                nullable = "NULLABLE" if col.get("nullable") else "NOT NULL"
                lines.append(f"    - {col['name']} ({col['type']}, {nullable})")

            lines.append("")

        physical_schema = "\n".join(lines)
        semantic_summary = semantic_loader.format_for_prompt()

        # 物理 Schema 解决“有哪些表字段”，语义层解决“业务词应该如何计算”
        return "\n".join([
            "物理数据库 Schema:",
            physical_schema,
            "",
            "业务语义层:",
            semantic_summary,
        ])

    def _extract_columns(self, sql: str) -> list[str]:
        """
        从 SQL 语句中提取使用的列名

        使用 SQLGlot 解析 SQL AST，遍历所有 Column 节点提取列名。
        这比让 LLM 返回 columns 更可靠，因为 LLM 可能遗漏或编造列名。
        """
        try:
            parsed = sqlglot.parse_one(sql, dialect="duckdb")
            columns = set()

            # 遍历 AST 中所有 Column 类型的节点
            for col in parsed.find_all(sqlglot.exp.Column):
                # col.name 是列名，col.table 是表名（可能为空）
                if col.name:
                    columns.add(col.name)

            return sorted(columns)
        except Exception:
            # SQL 解析失败不影响主流程，返回空列表
            return []


# 全局 SQL 生成器实例
sql_generator = SQLGenerator()
