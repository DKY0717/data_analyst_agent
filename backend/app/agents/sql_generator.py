# SQL 生成 Agent 模块
# 将用户的自然语言问题转换为可执行的 SQL 查询
# 是 LangGraph pipeline 中的第一个节点

import sqlglot
from sqlglot.tokens import Token, TokenType, Tokenizer
from typing import Dict, Any

from ..services.llm_service import llm_client
from ..models.schemas import SQLGeneratorOutput
from ..semantic.semantic_loader import semantic_loader
from ..utils.schema_formatter import format_physical_schema
from ..utils.logger import logger
from ..utils.exceptions import LLMError
from ..services.tracing import build_sql_metadata


_RESERVED_ALIAS_TYPES = {TokenType.AND, TokenType.OR}
_ALIAS_FOLLOW_TYPES = {
    TokenType.ON,
    TokenType.USING,
    TokenType.WHERE,
    TokenType.GROUP_BY,
    TokenType.ORDER_BY,
    TokenType.HAVING,
    TokenType.QUALIFY,
    TokenType.LIMIT,
    TokenType.JOIN,
    TokenType.LEFT,
    TokenType.RIGHT,
    TokenType.FULL,
    TokenType.INNER,
    TokenType.CROSS,
    TokenType.COMMA,
    TokenType.R_PAREN,
    TokenType.SEMICOLON,
}


class SQLGenerator:
    """SQL 生成 Agent，负责自然语言 → SQL 的转换"""

    def __init__(self, client=None):
        # 允许评测注入确定性 Fake LLM；生产默认仍使用统一 OpenAI-compatible client。
        self._client = client

    @property
    def client(self):
        """未注入时动态读取全局 client，保留现有运行时替换和测试能力。"""
        return self._client or llm_client

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
            result = await self.client.generate_sql(
                question,
                schema_str,
                conversation_context,
                intent_str,
            )

            # LLM 负责提出 SQL，Grounding 负责约束稳定的结果列契约。
            normalized_sql = self._normalize_reserved_table_aliases(result["sql"])
            normalized_sql = self._enforce_grounded_dimension_aliases(
                normalized_sql,
                analysis_intent,
            )

            # 从生成的 SQL 中提取使用的列名（LLM 返回的 tables 不含 columns）
            columns = self._extract_columns(normalized_sql)

            # 构造标准化输出
            output = SQLGeneratorOutput(
                sql=normalized_sql,
                tables=result.get("tables", []),
                columns=columns,
                explanation=result.get("explanation", "")
            )

            metadata = build_sql_metadata(output.sql)
            logger.info(
                "SQL 生成成功: hash=%s type=%s tables=%s",
                metadata["hash"],
                metadata["statement_type"],
                metadata["tables"],
            )
            return output

        except (KeyError, TypeError) as e:
            # LLM 返回的 JSON 缺少必要字段
            logger.error("SQL 生成结果格式错误: %s", type(e).__name__)
            raise LLMError("SQL 生成结果格式错误") from e
        except LLMError:
            # LLM 调用本身失败，直接向上抛
            raise
        except Exception as e:
            logger.error("SQL 生成异常: %s", type(e).__name__)
            raise LLMError("SQL 生成失败") from e

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

    def _enforce_grounded_dimension_aliases(
        self,
        sql: str,
        analysis_intent: Dict[str, Any] | None,
    ) -> str:
        """把直接物理维度列的自由别名恢复为 Grounding 稳定候选 ID。"""
        grounding = (analysis_intent or {}).get("grounding") or {}
        dimension_groundings = grounding.get("dimension_groundings") or []
        if not dimension_groundings:
            return sql

        try:
            parsed = sqlglot.parse_one(sql, dialect="duckdb")
        except Exception:
            # 解析失败交给后续 SQL Guard 统一处理，不在生成节点隐藏原始错误。
            return sql
        if not isinstance(parsed, sqlglot.exp.Select):
            return sql

        alias_contracts: dict[tuple[str, str], str] = {}
        concept_aliases: dict[str, str] = {}
        for item in dimension_groundings:
            candidates = item.get("candidates") or []
            if not candidates:
                continue
            candidate = max(
                candidates,
                key=lambda value: float(value.get("score") or 0.0),
            )
            expected_alias = str(candidate.get("candidate_id") or "").strip()
            source_column = self._direct_dimension_column(candidate.get("expression"))
            if expected_alias and source_column:
                alias_contracts[source_column] = expected_alias
                concept = str(item.get("concept") or "").strip().casefold()
                if concept:
                    concept_aliases[concept] = expected_alias

        table_aliases = {
            table.alias_or_name.casefold(): table.name.casefold()
            for table in parsed.find_all(sqlglot.exp.Table)
            if table.alias_or_name
            and table.name
            and table.find_ancestor(sqlglot.exp.Select) is parsed
        }

        aliases_by_physical_table: dict[str, list[str]] = {}
        for query_alias, physical_name in table_aliases.items():
            aliases_by_physical_table.setdefault(physical_name, []).append(query_alias)
        # 自连接存在多个查询别名时不能猜测应替换哪一个，保持 fail-closed。
        physical_aliases = {
            physical_name: query_aliases[0]
            for physical_name, query_aliases in aliases_by_physical_table.items()
            if len(query_aliases) == 1
        }

        normalized_count = 0
        alias_replacements: dict[str, str] = {}
        matched_contracts: set[tuple[str, str]] = set()
        for projection in parsed.expressions:
            expression = (
                projection.this if isinstance(projection, sqlglot.exp.Alias) else projection
            )
            if not isinstance(expression, sqlglot.exp.Column):
                continue
            source_column = self._resolved_column(expression, table_aliases)
            expected_alias = alias_contracts.get(source_column)
            if not expected_alias:
                continue
            matched_contracts.add(source_column)
            if isinstance(projection, sqlglot.exp.Alias):
                current_alias = projection.alias.casefold()
                if current_alias != expected_alias.casefold():
                    alias_replacements[current_alias] = expected_alias
                    projection.set("alias", sqlglot.exp.to_identifier(expected_alias))
                    normalized_count += 1

        missing_contracts = [
            source_column
            for source_column in alias_contracts
            if source_column not in matched_contracts
        ]
        direct_projections = [
            projection
            for projection in parsed.expressions
            if isinstance(
                projection.this if isinstance(projection, sqlglot.exp.Alias) else projection,
                sqlglot.exp.Column,
            )
        ]
        if (
            len(alias_contracts) == 1
            and len(missing_contracts) == 1
            and len(direct_projections) == 1
        ):
            projection = direct_projections[0]
            expression = (
                projection.this if isinstance(projection, sqlglot.exp.Alias) else projection
            )
            old_source = self._resolved_column(expression, table_aliases)
            expected_source = missing_contracts[0]
            expected_query_alias = physical_aliases.get(expected_source[0])
            if old_source != expected_source and expected_query_alias:
                old_output_name = projection.alias_or_name.casefold()
                self._replace_grouping_column(
                    parsed,
                    old_source,
                    expected_source,
                    expected_query_alias,
                    table_aliases,
                )
                expected_alias = alias_contracts[expected_source]
                if isinstance(projection, sqlglot.exp.Alias):
                    projection.set("alias", sqlglot.exp.to_identifier(expected_alias))
                alias_replacements[old_output_name] = expected_alias
                normalized_count += 1

        output_names = {
            projection.alias_or_name.casefold()
            for projection in parsed.expressions
            if projection.alias_or_name
        }
        for concept, expected_alias in concept_aliases.items():
            if expected_alias.casefold() in output_names:
                alias_replacements[concept] = expected_alias
        normalized_count += self._rewrite_clause_aliases(parsed, alias_replacements)

        if not normalized_count:
            return sql
        logger.info("已按 Grounding 规范化 %s 个维度输出别名", normalized_count)
        return parsed.sql(dialect="duckdb")

    @staticmethod
    def _resolved_column(
        column: sqlglot.exp.Column,
        table_aliases: dict[str, str],
    ) -> tuple[str, str]:
        """把查询别名还原为物理表名，供 Grounding 契约精确比对。"""
        query_table = column.table.casefold()
        return (
            table_aliases.get(query_table, query_table),
            column.name.casefold(),
        )

    def _replace_grouping_column(
        self,
        parsed: sqlglot.exp.Select,
        old_source: tuple[str, str],
        expected_source: tuple[str, str],
        expected_query_alias: str,
        table_aliases: dict[str, str],
    ) -> None:
        """只改写顶层投影、GROUP BY 和 ORDER BY，绝不触碰 JOIN/过滤条件。"""
        replacement = sqlglot.exp.column(
            expected_source[1],
            table=expected_query_alias,
        )
        for projection in parsed.expressions:
            expression = (
                projection.this if isinstance(projection, sqlglot.exp.Alias) else projection
            )
            if (
                isinstance(expression, sqlglot.exp.Column)
                and self._resolved_column(expression, table_aliases) == old_source
            ):
                expression.replace(replacement.copy())

        for container in (parsed.args.get("group"), parsed.args.get("order")):
            if container is None:
                continue
            for column in list(container.find_all(sqlglot.exp.Column)):
                if column.find_ancestor(sqlglot.exp.Select) is not parsed:
                    continue
                if self._resolved_column(column, table_aliases) == old_source:
                    column.replace(replacement.copy())

    @staticmethod
    def _rewrite_clause_aliases(
        parsed: sqlglot.exp.Select,
        replacements: dict[str, str],
    ) -> int:
        """同步改写排序/分组中的旧语义别名，避免权限 Guard 将其当成裸字段。"""
        if not replacements:
            return 0
        changed = 0
        for clause_name in ("group", "order", "having", "qualify"):
            clause = parsed.args.get(clause_name)
            if clause is None:
                continue
            for column in clause.find_all(sqlglot.exp.Column):
                if column.table or column.find_ancestor(sqlglot.exp.Select) is not parsed:
                    continue
                expected_alias = replacements.get(column.name.casefold())
                if expected_alias and expected_alias.casefold() != column.name.casefold():
                    column.set("this", sqlglot.exp.to_identifier(expected_alias))
                    changed += 1
        return changed

    @staticmethod
    def _normalize_reserved_table_aliases(sql: str) -> str:
        """在 AST 解析前替换 AND/OR 表别名；仅处理明确的 FROM/JOIN alias 位置。"""
        if not isinstance(sql, str) or not sql.strip():
            return sql

        try:
            tokens = Tokenizer(dialect="duckdb").tokenize(sql)
        except Exception:
            # Tokenizer 也无法识别时保留原 SQL，由 SQL Guard 给出统一错误。
            return sql

        used_identifiers = {
            token.text.casefold()
            for token in tokens
            if token.token_type in {TokenType.VAR, TokenType.IDENTIFIER}
        }
        replacements: dict[str, str] = {}
        declaration_indexes = {
            index
            for index, token in enumerate(tokens)
            if token.token_type in _RESERVED_ALIAS_TYPES
            and SQLGenerator._is_reserved_alias_declaration(tokens, index)
        }
        for index in declaration_indexes:
            normalized_alias = tokens[index].text.casefold()
            base = f"{normalized_alias}_table"
            safe_alias = base
            suffix = 2
            while safe_alias.casefold() in used_identifiers:
                safe_alias = f"{base}_{suffix}"
                suffix += 1
            replacements[normalized_alias] = safe_alias
            used_identifiers.add(safe_alias.casefold())

        token_replacements: list[tuple[int, int, str]] = []
        for index, token in enumerate(tokens):
            normalized_alias = token.text.casefold()
            if normalized_alias not in replacements:
                continue
            is_qualifier = index + 1 < len(tokens) and tokens[index + 1].token_type == TokenType.DOT
            if index in declaration_indexes or is_qualifier:
                token_replacements.append(
                    (token.start, token.end + 1, replacements[normalized_alias])
                )

        normalized_sql = sql
        for start, end, replacement in sorted(token_replacements, reverse=True):
            normalized_sql = normalized_sql[:start] + replacement + normalized_sql[end:]
        if replacements:
            logger.info("已规范化 %s 个 SQL 保留字表别名", len(replacements))
        return normalized_sql

    @staticmethod
    def _is_reserved_alias_declaration(tokens: list[Token], index: int) -> bool:
        """识别 FROM/JOIN 后的表别名位置，避免把逻辑 AND/OR 当成别名。"""
        next_type = tokens[index + 1].token_type if index + 1 < len(tokens) else None
        if next_type is not None and next_type not in _ALIAS_FOLLOW_TYPES:
            return False

        cursor = index - 1
        if cursor >= 0 and tokens[cursor].token_type == TokenType.ALIAS:
            cursor -= 1
        if cursor < 0 or tokens[cursor].token_type not in {
            TokenType.VAR,
            TokenType.IDENTIFIER,
        }:
            return False
        cursor -= 1
        while (
            cursor >= 1
            and tokens[cursor].token_type == TokenType.DOT
            and tokens[cursor - 1].token_type in {TokenType.VAR, TokenType.IDENTIFIER}
        ):
            cursor -= 2
        return cursor >= 0 and tokens[cursor].token_type in {
            TokenType.FROM,
            TokenType.JOIN,
        }

    @staticmethod
    def _direct_dimension_column(expression: object) -> tuple[str, str] | None:
        """仅接受单个直接物理列；派生维度表达式保持模型原样并交给 Guard。"""
        if not isinstance(expression, str) or not expression.strip():
            return None
        try:
            parsed = sqlglot.parse_one(
                f"SELECT {expression}",
                dialect="duckdb",
            )
        except Exception:
            return None
        if not isinstance(parsed, sqlglot.exp.Select) or len(parsed.expressions) != 1:
            return None
        projection = parsed.expressions[0]
        if not isinstance(projection, sqlglot.exp.Column) or not projection.table:
            return None
        return projection.table.casefold(), projection.name.casefold()

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

        # Grounding 信息：指标和维度的物理表达式
        grounding = analysis_intent.get("grounding", {})
        metric_groundings = grounding.get("metric_groundings", [])
        if metric_groundings:
            lines.append("指标 Grounding:")
            for mg in metric_groundings:
                candidates = mg.get("candidates", [])
                if candidates:
                    best = candidates[0]
                    lines.append(f"  - {mg['concept']}: {best['expression']}")

        dimension_groundings = grounding.get("dimension_groundings", [])
        if dimension_groundings:
            lines.append("维度 Grounding:")
            for dg in dimension_groundings:
                candidates = dg.get("candidates", [])
                if candidates:
                    best = candidates[0]
                    lines.append(f"  - {dg['concept']}: {best['expression']}")
                    if best.get("tables"):
                        lines.append(f"    需要表: {', '.join(best['tables'])}")

        # Schema 路由：需要的表和 JOIN
        route = grounding.get("schema_route", {})
        if route.get("join_edges"):
            lines.append("需要 JOIN:")
            for edge in route["join_edges"]:
                lines.append(f"  - {edge[0]} = {edge[1]}")

        return "\n".join(lines)


# 全局 SQL 生成器实例
sql_generator = SQLGenerator()
