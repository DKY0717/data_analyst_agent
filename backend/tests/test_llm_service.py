# LLM 服务测试
# 测试 QwenAPIClient 的核心功能：JSON 解析、结果格式化、异常处理

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm_service import QwenAPIClient
from app.services.llm_observability import get_calls, start_trace
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
        """测试请求体结构正确（OpenAI 兼容格式）"""
        messages = [{"role": "user", "content": "测试"}]
        payload = client._build_payload(messages, 0.1, 1000)

        assert payload["model"] == client.model
        assert payload["messages"] == messages
        assert payload["temperature"] == 0.1
        assert payload["max_tokens"] == 1000


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

        async def fake_call_api(messages, temperature, max_tokens=2000, stage="unknown"):
            captured_messages["messages"] = messages
            return '{"sql": "SELECT SUM(total_amount) FROM orders", "tables": ["orders"], "explanation": "统计销售额"}'

        client._call_api = fake_call_api

        await client.generate_sql("统计销售额", "业务语义层:\n- 销售额 = SUM(orders.total_amount)")

        system_prompt = captured_messages["messages"][0]["content"]
        user_prompt = captured_messages["messages"][1]["content"]

        assert "优先遵循业务语义层" in system_prompt
        assert "业务指标口径" in system_prompt
        assert "稳定英文 key 作为输出别名" in system_prompt
        assert "粒度覆盖表达式" in system_prompt
        assert "业务语义层" in user_prompt

    @pytest.mark.asyncio
    async def test_generate_sql_prompt_includes_conversation_context(self, client):
        captured_messages = {}

        async def fake_call_api(messages, temperature, max_tokens=2000, stage="unknown"):
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


class TestParseAnalysisIntentPrompt:
    """测试分析意图 Prompt 只要求业务概念，不提前绑定物理 Schema。"""

    @pytest.mark.asyncio
    async def test_parse_analysis_intent_requests_structured_business_intent(self, client):
        captured = {}

        async def fake_call_api(messages, temperature, max_tokens=2000, stage="unknown"):
            captured["messages"] = messages
            captured["stage"] = stage
            return '{"task_types": ["aggregation"], "metrics": [], "dimensions": [], "filters": [], "missing_slots": ["metric"], "overall_confidence": 0.4}'

        client._call_api = fake_call_api

        result = await client.parse_analysis_intent("分析经营情况", "业务指标: 销售额")

        system_prompt = captured["messages"][0]["content"]
        assert captured["stage"] == "parse_analysis_intent"
        assert "禁止输出 SQL" in system_prompt
        assert "禁止输出物理表名" in system_prompt
        assert result["missing_slots"] == ["metric"]


class TestRepairSQLPrompt:
    """测试 SQL Repair prompt 是否包含已验证的 DuckDB 修复约束"""

    @pytest.mark.asyncio
    async def test_repair_prompt_includes_duckdb_date_and_cast_guidance(self, client):
        captured_messages = {}

        async def fake_call_api(messages, temperature, max_tokens=2000, stage="unknown"):
            captured_messages["messages"] = messages
            return '{"repaired_sql": "SELECT EXTRACT(QUARTER FROM order_date) FROM orders", "repair_reason": "使用 DuckDB 季度函数"}'

        client._call_api = fake_call_api

        await client.repair_sql(
            "SELECT strftime(order_date, '%q') FROM orders",
            "Unrecognized format for strftime/strptime: %q",
            "表名: orders\n字段: order_date (DATE)",
        )

        system_prompt = captured_messages["messages"][0]["content"]

        assert "EXTRACT(QUARTER FROM date_column)" in system_prompt
        assert "字符串参与算术前必须显式 CAST" in system_prompt


class FakeHTTPResponse:
    def __init__(self, payload, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, outcomes):
        self.outcomes = outcomes

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class TestCallAPIObservability:
    """测试 Qwen API 边界能记录真实 usage、耗时、尝试次数与失败类型"""

    @pytest.mark.asyncio
    async def test_successful_call_records_usage(self, client, monkeypatch):
        start_trace()
        outcomes = [
            FakeHTTPResponse(
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 30,
                        "total_tokens": 150,
                    },
                }
            )
        ]
        monkeypatch.setattr(
            "app.services.llm_service.httpx.AsyncClient",
            lambda: FakeAsyncClient(outcomes),
        )

        content = await client._call_api([], 0.1, stage="generate_sql")

        assert content == "ok"
        assert get_calls()[0] | {"latency_ms": 0} == {
            "stage": "generate_sql",
            "model": client.model,
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "latency_ms": 0,
            "attempt_count": 1,
            "estimated_cost": None,
            "success": True,
            "error_type": None,
        }

    @pytest.mark.asyncio
    async def test_missing_usage_records_zero_tokens(self, client, monkeypatch):
        start_trace()
        outcomes = [
            FakeHTTPResponse({"choices": [{"message": {"content": "ok"}}]})
        ]
        monkeypatch.setattr(
            "app.services.llm_service.httpx.AsyncClient",
            lambda: FakeAsyncClient(outcomes),
        )

        await client._call_api([], 0.1, stage="generate_answer")

        assert get_calls()[0]["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_retry_then_success_records_one_call_with_attempt_count(self, client, monkeypatch):
        start_trace()
        outcomes = [
            RuntimeError("temporary network error"),
            FakeHTTPResponse(
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            ),
        ]
        monkeypatch.setattr(
            "app.services.llm_service.httpx.AsyncClient",
            lambda: FakeAsyncClient(outcomes),
        )

        async def no_sleep(seconds):
            return None

        monkeypatch.setattr("asyncio.sleep", no_sleep)

        await client._call_api([], 0.1, stage="repair_sql")

        assert len(get_calls()) == 1
        assert get_calls()[0]["attempt_count"] == 2
        assert get_calls()[0]["total_tokens"] == 15
        assert get_calls()[0]["success"] is True

    @pytest.mark.asyncio
    async def test_final_failure_records_error_type_without_error_message(self, client, monkeypatch):
        start_trace()
        outcomes = [RuntimeError("secret server response")] * client.max_retries
        monkeypatch.setattr(
            "app.services.llm_service.httpx.AsyncClient",
            lambda: FakeAsyncClient(outcomes),
        )

        async def no_sleep(seconds):
            return None

        monkeypatch.setattr("asyncio.sleep", no_sleep)

        with pytest.raises(LLMError):
            await client._call_api([], 0.1, stage="repair_sql")

        call = get_calls()[0]
        assert call["success"] is False
        assert call["attempt_count"] == client.max_retries
        assert call["error_type"] == "RuntimeError"
        assert "secret server response" not in str(call)
