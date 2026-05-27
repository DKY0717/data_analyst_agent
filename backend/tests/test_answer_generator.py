# Answer Generator Agent 测试
# 测试答案生成 Agent 的核心功能：异常处理、LLM 调用

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.answer_generator import AnswerGenerator
from app.utils.exceptions import LLMError


@pytest.fixture
def generator():
    """创建测试用的答案生成器实例"""
    return AnswerGenerator()


@pytest.fixture
def mock_query_result():
    """模拟查询结果数据"""
    return {
        "success": True,
        "columns": ["month", "sales"],
        "rows": [
            ["2024-01", 12000.50],
            ["2024-02", 14500.80],
            ["2024-03", 13200.00]
        ],
        "execution_time_ms": 42,
        "row_count": 3
    }


class TestGenerate:
    """测试答案生成功能"""

    @pytest.mark.asyncio
    async def test_generate_success(self, generator, mock_query_result):
        """测试成功生成答案"""
        mock_answer = "2024年第一季度销售额呈上升趋势，1月为12000.50元，2月为14500.80元，3月为13200.00元。"

        with patch("app.agents.answer_generator.llm_client") as mock_llm:
            mock_llm.generate_answer = AsyncMock(return_value=mock_answer)

            result = await generator.generate(
                "统计2024年每月销售额",
                "SELECT month, sales FROM orders",
                mock_query_result
            )

            # 验证返回结果
            assert isinstance(result, str)
            assert "12000.50" in result
            assert "14500.80" in result

            # 验证 LLM 被正确调用
            mock_llm.generate_answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_llm_error(self, generator, mock_query_result):
        """测试 LLM 调用失败时抛出异常"""
        with patch("app.agents.answer_generator.llm_client") as mock_llm:
            mock_llm.generate_answer = AsyncMock(side_effect=Exception("API 调用失败"))

            with pytest.raises(LLMError) as exc_info:
                await generator.generate(
                    "测试问题",
                    "SELECT 1",
                    mock_query_result
                )

            assert "答案生成失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_empty_result(self, generator):
        """测试查询结果为空时生成答案"""
        empty_result = {
            "success": True,
            "columns": ["id", "name"],
            "rows": [],
            "execution_time_ms": 10,
            "row_count": 0
        }

        mock_answer = "查询结果为空，没有符合条件的数据。"

        with patch("app.agents.answer_generator.llm_client") as mock_llm:
            mock_llm.generate_answer = AsyncMock(return_value=mock_answer)

            result = await generator.generate(
                "查询所有商品",
                "SELECT id, name FROM products",
                empty_result
            )

            assert "为空" in result

    @pytest.mark.asyncio
    async def test_generate_failed_query(self, generator):
        """测试查询失败时生成答案"""
        failed_result = {
            "success": False,
            "error": "Table does not exist",
            "error_type": "CatalogException"
        }

        mock_answer = "查询失败，原因是表不存在。"

        with patch("app.agents.answer_generator.llm_client") as mock_llm:
            mock_llm.generate_answer = AsyncMock(return_value=mock_answer)

            result = await generator.generate(
                "查询不存在的表",
                "SELECT * FROM non_existent",
                failed_result
            )

            assert "失败" in result
