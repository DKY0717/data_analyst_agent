# SQL Repair Agent 测试
# 测试 SQL 修复 Agent 的核心功能：Schema 格式化、修复流程、异常处理

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.sql_repair import SQLRepairAgent
from app.models.schemas import SQLRepairOutput
from app.utils.exceptions import SQLRepairError


@pytest.fixture
def repair_agent():
    """创建测试用的 SQL 修复器实例"""
    return SQLRepairAgent()


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
            }
        }
    }


class TestFormatSchema:
    """测试 Schema 格式化功能"""

    def test_format_schema_output(self, repair_agent, mock_schema):
        """测试 Schema 格式化输出"""
        result = repair_agent._format_schema(mock_schema)

        # 验证表名
        assert "表名: orders" in result

        # 验证主键
        assert "主键: order_id" in result

        # 验证字段
        assert "order_id (INTEGER, NOT NULL)" in result
        assert "customer_id (INTEGER, NULLABLE)" in result
        assert "total_amount (DECIMAL, NOT NULL)" in result

    def test_format_schema_empty(self, repair_agent):
        """测试空 Schema 格式化"""
        schema = {"tables": {}}
        result = repair_agent._format_schema(schema)
        assert result == ""


class TestRepair:
    """测试 SQL 修复功能"""

    @pytest.mark.asyncio
    async def test_repair_success(self, repair_agent, mock_schema):
        """测试成功修复 SQL"""
        # Mock LLM 返回
        mock_response = {
            "repaired_sql": "SELECT order_id, total_amount FROM orders",
            "repair_reason": "原 SQL 使用了不存在的字段 amount，已改为 total_amount"
        }

        with patch("app.agents.sql_repair.llm_client") as mock_llm:
            mock_llm.repair_sql = AsyncMock(return_value=mock_response)

            result = await repair_agent.repair(
                "SELECT order_id, amount FROM orders",
                "column amount does not exist",
                mock_schema
            )

            # 验证返回结果
            assert isinstance(result, SQLRepairOutput)
            assert result.repaired_sql == "SELECT order_id, total_amount FROM orders"
            assert "total_amount" in result.repair_reason

            # 验证 LLM 被正确调用
            mock_llm.repair_sql.assert_called_once()

    @pytest.mark.asyncio
    async def test_repair_llm_error(self, repair_agent, mock_schema):
        """测试 LLM 调用失败时抛出异常"""
        with patch("app.agents.sql_repair.llm_client") as mock_llm:
            mock_llm.repair_sql = AsyncMock(side_effect=Exception("API 调用失败"))

            with pytest.raises(SQLRepairError) as exc_info:
                await repair_agent.repair(
                    "SELECT * FROM orders",
                    "some error",
                    mock_schema
                )

            assert "SQL 修复失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_repair_missing_repaired_sql(self, repair_agent, mock_schema):
        """测试 LLM 返回缺少 repaired_sql 字段时抛出异常"""
        # 返回缺少必要字段的 JSON
        mock_response = {
            "repair_reason": "修复了字段名"
        }

        with patch("app.agents.sql_repair.llm_client") as mock_llm:
            mock_llm.repair_sql = AsyncMock(return_value=mock_response)

            with pytest.raises(SQLRepairError) as exc_info:
                await repair_agent.repair(
                    "SELECT * FROM orders",
                    "some error",
                    mock_schema
                )

            assert "格式错误" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_repair_with_complex_schema(self, repair_agent):
        """测试复杂 Schema 下的修复"""
        complex_schema = {
            "tables": {
                "orders": {
                    "table_name": "orders",
                    "columns": [
                        {"name": "order_id", "type": "INTEGER", "nullable": False},
                        {"name": "customer_id", "type": "INTEGER", "nullable": True}
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

        mock_response = {
            "repaired_sql": "SELECT o.order_id, c.customer_name FROM orders o JOIN customers c ON o.customer_id = c.customer_id",
            "repair_reason": "添加了 JOIN 来关联客户表"
        }

        with patch("app.agents.sql_repair.llm_client") as mock_llm:
            mock_llm.repair_sql = AsyncMock(return_value=mock_response)

            result = await repair_agent.repair(
                "SELECT order_id, customer_name FROM orders",
                "column customer_name does not exist",
                complex_schema
            )

            assert "JOIN" in result.repaired_sql
            assert "customers" in result.repaired_sql
