# SQL Generator Agent 测试
# 测试 SQL 生成 Agent 的核心功能：Schema 格式化、列名提取、异常处理

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.sql_generator import SQLGenerator, llm_client
from app.models.schemas import SQLGeneratorOutput
from app.utils.exceptions import LLMError


@pytest.fixture
def generator():
    """创建测试用的 SQL 生成器实例"""
    return SQLGenerator()


@pytest.fixture
def mock_schema():
    """模拟数据库 Schema 数据"""
    return {
        "tables": {
            "orders": {
                "table_name": "orders",
                "columns": [
                    {"name": "order_id", "type": "INTEGER", "nullable": False},
                    {"name": "customer_id", "type": "INTEGER", "nullable": True},
                    {"name": "total_amount", "type": "DECIMAL", "nullable": False}
                ],
                "primary_keys": ["order_id"]
            },
            "customers": {
                "table_name": "customers",
                "columns": [
                    {"name": "customer_id", "type": "INTEGER", "nullable": False},
                    {"name": "customer_name", "type": "VARCHAR", "nullable": False}
                ],
                "primary_keys": ["customer_id"]
            }
        }
    }


class TestFormatSchema:
    """测试 Schema 格式化功能"""

    def test_format_schema_with_primary_keys(self, generator, mock_schema):
        """测试包含主键的 Schema 格式化"""
        result = generator._format_schema(mock_schema)

        # 验证表名存在
        assert "表名: orders" in result
        assert "表名: customers" in result

        # 验证主键标注
        assert "主键: order_id" in result
        assert "主键: customer_id" in result

        # 验证字段信息
        assert "order_id (INTEGER, NOT NULL)" in result
        assert "customer_id (INTEGER, NULLABLE)" in result
        assert "total_amount (DECIMAL, NOT NULL)" in result

    def test_format_schema_includes_semantic_summary(self, generator):
        """SQL Generator 给 LLM 的上下文必须包含业务语义层摘要"""
        schema_context = {
            "tables": {
                "orders": {
                    "table_name": "orders",
                    "columns": [
                        {"name": "order_id", "type": "INTEGER", "nullable": False},
                        {"name": "total_amount", "type": "DECIMAL", "nullable": False},
                    ],
                    "primary_keys": ["order_id"],
                }
            }
        }

        result = generator._format_schema(schema_context)

        assert "物理数据库 Schema:" in result
        assert "业务语义层:" in result
        assert "销售额 = SUM(orders.total_amount)" in result
        assert "默认时间字段: orders.order_date" in result

    def test_format_schema_empty_tables(self, generator):
        """测试空 Schema 的格式化"""
        schema = {"tables": {}}
        result = generator._format_schema(schema)
        assert "物理数据库 Schema:" in result
        assert "业务语义层:" in result

    def test_format_schema_no_primary_keys(self, generator):
        """测试没有主键的 Schema 格式化"""
        schema = {
            "tables": {
                "logs": {
                    "table_name": "logs",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "nullable": False}
                    ],
                    "primary_keys": []
                }
            }
        }
        result = generator._format_schema(schema)
        assert "表名: logs" in result
        assert "  主键" not in result


class TestExtractColumns:
    """测试列名提取功能"""

    def test_extract_columns_simple_select(self, generator):
        """测试从简单 SELECT 中提取列名"""
        sql = "SELECT order_id, customer_id FROM orders"
        columns = generator._extract_columns(sql)
        assert "order_id" in columns
        assert "customer_id" in columns

    def test_extract_columns_with_alias(self, generator):
        """测试从带别名的 SQL 中提取列名"""
        sql = "SELECT o.order_id AS id, o.total_amount AS amount FROM orders o"
        columns = generator._extract_columns(sql)
        assert "order_id" in columns
        assert "total_amount" in columns

    def test_extract_columns_with_join(self, generator):
        """测试从 JOIN 查询中提取列名"""
        sql = """
        SELECT o.order_id, c.customer_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        """
        columns = generator._extract_columns(sql)
        assert "order_id" in columns
        assert "customer_name" in columns
        assert "customer_id" in columns

    def test_extract_columns_invalid_sql(self, generator):
        """测试无效 SQL 时返回空列表"""
        sql = "这不是 SQL 语句"
        columns = generator._extract_columns(sql)
        assert columns == []


class TestGenerate:
    """测试 SQL 生成功能"""

    @pytest.mark.asyncio
    async def test_generate_success(self, generator, mock_schema, caplog):
        """测试成功生成 SQL"""
        # Mock LLM 返回
        mock_response = {
            "sql": "SELECT COUNT(*) AS order_count FROM orders WHERE customer_name = 'private-customer'",
            "tables": ["orders"],
            "explanation": "统计订单总数"
        }

        with patch("app.agents.sql_generator.llm_client") as mock_llm:
            mock_llm.generate_sql = AsyncMock(return_value=mock_response)

            result = await generator.generate("统计订单总数", mock_schema)

            # 验证返回结果
            assert isinstance(result, SQLGeneratorOutput)
            assert "private-customer" in result.sql
            assert "orders" in result.tables
            assert result.explanation == "统计订单总数"
            assert "private-customer" not in caplog.text
            assert "hash=" in caplog.text

            # 验证 LLM 被正确调用
            mock_llm.generate_sql.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_llm_error(self, generator, mock_schema):
        """测试 LLM 调用失败时抛出异常"""
        with patch("app.agents.sql_generator.llm_client") as mock_llm:
            mock_llm.generate_sql = AsyncMock(side_effect=LLMError("API 调用失败"))

            with pytest.raises(LLMError) as exc_info:
                await generator.generate("测试问题", mock_schema)

            # sql_generator 对 LLMError 直接向上抛，不包装
            assert "API 调用失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_missing_sql_field(self, generator, mock_schema):
        """测试 LLM 返回缺少 sql 字段时抛出异常"""
        # 返回缺少 sql 字段的 JSON
        mock_response = {
            "tables": ["orders"],
            "explanation": "测试"
        }

        with patch("app.agents.sql_generator.llm_client") as mock_llm:
            mock_llm.generate_sql = AsyncMock(return_value=mock_response)

            with pytest.raises(LLMError) as exc_info:
                await generator.generate("测试问题", mock_schema)

            assert "格式错误" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_passes_semantic_context_to_llm(self, generator):
        """生成 SQL 时传给 LLM 的 schema_info 应包含物理 Schema 和业务语义"""
        schema_context = {
            "tables": {
                "orders": {
                    "table_name": "orders",
                    "columns": [
                        {"name": "order_id", "type": "INTEGER", "nullable": False},
                        {"name": "total_amount", "type": "DECIMAL", "nullable": False},
                        {"name": "order_date", "type": "DATE", "nullable": False},
                    ],
                    "primary_keys": ["order_id"],
                }
            }
        }

        captured = {}

        async def fake_generate_sql(question, schema_info, conversation_context="", analysis_intent=""):
            captured["question"] = question
            captured["schema_info"] = schema_info
            captured["conversation_context"] = conversation_context
            captured["analysis_intent"] = analysis_intent
            return {
                "sql": "SELECT SUM(orders.total_amount) AS sales_amount FROM orders",
                "tables": ["orders"],
                "explanation": "统计销售额",
            }

        original_generate_sql = llm_client.generate_sql
        llm_client.generate_sql = fake_generate_sql
        try:
            output = await generator.generate("统计销售额", schema_context)
        finally:
            llm_client.generate_sql = original_generate_sql

        assert output.sql == "SELECT SUM(orders.total_amount) AS sales_amount FROM orders"
        assert "表名: orders" in captured["schema_info"]
        assert "销售额 = SUM(orders.total_amount)" in captured["schema_info"]
        assert captured["conversation_context"] == ""

    @pytest.mark.asyncio
    async def test_generate_passes_conversation_context_to_llm(self, generator, mock_schema):
        """多轮追问时，SQL Generator 应把历史上下文传给 LLM Service"""
        mock_response = {
            "sql": "SELECT region_name, SUM(total_amount) AS sales FROM orders GROUP BY region_name",
            "tables": ["orders", "regions"],
            "explanation": "基于上一轮销售额按地区拆分",
        }

        with patch("app.agents.sql_generator.llm_client") as mock_llm:
            mock_llm.generate_sql = AsyncMock(return_value=mock_response)

            await generator.generate(
                "按地区拆一下",
                mock_schema,
                conversation_context="上一轮分析上下文:\n- 问题: 统计销售额",
            )

            assert mock_llm.generate_sql.call_args.args[2] == "上一轮分析上下文:\n- 问题: 统计销售额"
