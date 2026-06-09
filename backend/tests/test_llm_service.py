# LLM 服务测试
# 测试 QwenAPIClient 的核心功能：JSON 解析、结果格式化、异常处理

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm_service import QwenAPIClient
from app.utils.exceptions import LLMError, LLMTimeoutError, LLMResponseError


@pytest.fixture
def client():
    """创建测试用的客户端实例"""
    return QwenAPIClient()


class TestParseJsonResponse:
    """测试 JSON 响应解析功能"""

    def test_parse_valid_json(self, client):
        """测试解析标准 JSON 响应"""
        content = '{"sql": "SELECT * FROM orders", "tables": ["orders"], "explanation": "查询所有订单"}'
        result = client._parse_json_response(content, "测试")
        assert result["sql"] == "SELECT * FROM orders"
        assert result["tables"] == ["orders"]

    def test_parse_json_with_extra_text(self, client):
        """测试解析包含额外文字的 JSON 响应"""
        content = '根据您的需求，我生成了以下 SQL：\n{"sql": "SELECT 1", "tables": [], "explanation": "测试"}\n希望对您有帮助！'
        result = client._parse_json_response(content, "测试")
        assert result["sql"] == "SELECT 1"

    def test_parse_invalid_json_raises_error(self, client):
        """测试解析无效 JSON 时抛出异常"""
        content = '这不是 JSON 格式的响应'
        with pytest.raises(LLMResponseError) as exc_info:
            client._parse_json_response(content, "测试")
        assert "不是有效的 JSON" in str(exc_info.value)


class TestFormatQueryResult:
    """测试查询结果格式化功能"""

    def test_format_empty_result(self, client):
        """测试格式化空结果"""
        result = client._format_query_result({"rows": []})
        assert result == "查询结果为空"

    def test_format_result_with_data(self, client):
        """测试格式化有数据的结果"""
        query_result = {
            "columns": ["id", "name"],
            "rows": [[1, "商品A"], [2, "商品B"]]
        }
        result = client._format_query_result(query_result)
        assert "列名: id, name" in result
        assert "共 2 条记录" in result
        assert "记录 1:" in result

    def test_format_result_truncates_long_output(self, client):
        """测试结果超过 10 条时截断显示"""
        query_result = {
            "columns": ["id"],
            "rows": [[i] for i in range(20)]
        }
        result = client._format_query_result(query_result)
        assert "共 20 条记录" in result
        assert "... 还有 10 条记录" in result


class TestBuildPayload:
    """测试请求体构建"""

    def test_build_payload_structure(self, client):
        """测试请求体结构正确"""
        messages = [{"role": "user", "content": "测试"}]
        payload = client._build_payload(messages, 0.1, 1000)

        assert payload["model"] == client.model
        assert payload["input"]["messages"] == messages
        assert payload["parameters"]["temperature"] == 0.1
        assert payload["parameters"]["max_tokens"] == 1000
        assert payload["parameters"]["result_format"] == "message"


class TestBuildHeaders:
    """测试请求头构建"""

    def test_build_headers_contains_auth(self, client):
        """测试请求头包含认证信息"""
        headers = client._build_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert headers["Content-Type"] == "application/json"


class TestGenerateSQLPrompt:
    """测试 SQL 生成 prompt 是否明确使用业务语义层"""

    @pytest.mark.asyncio
    async def test_generate_sql_prompt_mentions_semantic_layer(self, client):
        captured_messages = {}

        async def fake_call_api(messages, temperature, max_tokens=2000):
            captured_messages["messages"] = messages
            return '{"sql": "SELECT SUM(total_amount) FROM orders", "tables": ["orders"], "explanation": "统计销售额"}'

        client._call_api = fake_call_api

        await client.generate_sql("统计销售额", "业务语义层:\n- 销售额 = SUM(orders.total_amount)")

        system_prompt = captured_messages["messages"][0]["content"]
        user_prompt = captured_messages["messages"][1]["content"]

        assert "优先遵循业务语义层" in system_prompt
        assert "业务指标口径" in system_prompt
        assert "业务语义层" in user_prompt

    @pytest.mark.asyncio
    async def test_generate_sql_prompt_includes_conversation_context(self, client):
        captured_messages = {}

        async def fake_call_api(messages, temperature, max_tokens=2000):
            captured_messages["messages"] = messages
            return '{"sql": "SELECT region_name, SUM(total_amount) FROM orders GROUP BY region_name", "tables": ["orders"], "explanation": "按地区拆分"}'

        client._call_api = fake_call_api

        await client.generate_sql(
            "按地区拆一下",
            "业务语义层:\n- 销售额 = SUM(orders.total_amount)",
            "上一轮分析上下文:\n- 问题: 统计销售额",
        )

        system_prompt = captured_messages["messages"][0]["content"]
        user_prompt = captured_messages["messages"][1]["content"]

        assert "多轮追问" in system_prompt
        assert "多轮对话上下文" in user_prompt
        assert "上一轮分析上下文" in user_prompt
        assert "按地区拆一下" in user_prompt
