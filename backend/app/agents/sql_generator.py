# SQL 生成 Agent 模块
# 将用户的自然语言问题转换为可执行的 SQL 查询
# 是 LangGraph pipeline 中的第一个节点

import sqlglot
from typing import Dict, Any

from ..services.llm_service import llm_client
from ..models.schemas import SQLGeneratorOutput
from ..semantic.semantic_loader import semantic_loader
from ..utils.schema_formatter import format_physical_schema
from ..utils.logger import logger
from ..utils.exceptions import LLMError


class SQLGenerator:
    """SQL 生成 Agent，负责自然语言 → SQL 的转换"""

    async def generate(
        self,
        question: str,
        schema_context: Dict[str, Any],
        conversation_context: str = "",
        analysis_intent: Dict[str, Any] | None = None,
    ) -> SQLGeneratorOutput:
        """
        根据自然语言问题和数据库 Schema 生成 SQL

        Args:
            question: 用户的自然语言问题
            schema_context: 数据库 Schema 信息，来自 SchemaLoader.get_full_schema()
            conversation_context: 多轮追问上下文摘要；为空时按单轮查询处理
            analysis_intent: 分层意图解析结果，包含指标、维度、过滤、排序等结构化信号

        Returns:
            SQLGeneratorOutput: 包含 sql、tables、columns、explanation 的结构化结果

        Raises:
            LLMError: LLM 调用失败或返回无效结果时抛出
        """
        # 将 Schema 字典格式化为 LLM 可读的文本
        schema_str = self._format_schema(schema_context)

        # 将意图解析结果格式化为 LLM 可读的文本
        intent_str = self._format_intent(analysis_intent) if analysis_intent else ""

        try:
            # 调用 LLM 生成 SQL，返回结构化 JSON
            result = await llm_client.generate_sql(question, schema_str, conversation_context, intent_str)

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
        将 Schema 字典格式化为 LLM 可读的文本（物理 Schema + 语义层）
        """
        physical_schema = format_physical_schema(schema_context)
        semantic_summary = semantic_loader.format_for_prompt()

        # 物理 Schema 解决"有哪些表字段"，语义层解决"业务词应该如何计算"
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

    @staticmethod
    def _format_intent(analysis_intent: Dict[str, Any]) -> str:
        """将结构化意图解析结果格式化为 LLM 可读的文本"""
        lines = ["分析意图（结构化解析结果，优先参考）:"]

        metrics = analysis_intent.get("metrics", [])
        if metrics:
            concepts = ", ".join(m.get("concept", "") for m in metrics)
            lines.append(f"- 指标: {concepts}")

        dimensions = analysis_intent.get("dimensions", [])
        if dimensions:
            concepts = ", ".join(d.get("concept", "") for d in dimensions)
            lines.append(f"- 维度: {concepts}")

        filters = analysis_intent.get("filters", [])
        if filters:
            for f in filters:
                lines.append(f"- 过滤: {f.get('concept', '')} {f.get('operator', '')} {f.get('value', '')}")

        ranking = analysis_intent.get("ranking")
        if ranking:
            lines.append(f"- 排序: {ranking.get('direction', 'desc')} 前 {ranking.get('limit', '')} 名")

        time_granularity = analysis_intent.get("time_granularity")
        if time_granularity:
            lines.append(f"- 时间粒度: {time_granularity}")

        return "\n".join(lines)


# 全局 SQL 生成器实例
sql_generator = SQLGenerator()
