# LLM 分析意图解析器测试
# LLM 只补充复杂业务语义，输出必须经过稳定 Pydantic 契约校验。

from unittest.mock import AsyncMock

import pytest

from app.analysis_intent.llm_parser import AnalysisIntentLLMParser
from app.utils.exceptions import LLMResponseError


@pytest.mark.asyncio
async def test_llm_parser_returns_validated_intent():
    client = AsyncMock()
    client.parse_analysis_intent.return_value = {
        "task_types": ["aggregation"],
        "metrics": [
            {"concept": "refund_rate", "confidence": 0.9, "evidence": "退款率"}
        ],
        "dimensions": [
            {"concept": "region", "confidence": 0.9, "evidence": "地区"}
        ],
        "filters": [],
        "missing_slots": [],
        "overall_confidence": 0.9,
    }

    result = await AnalysisIntentLLMParser(client=client).parse("统计各地区退款率")

    assert result.metrics[0].concept == "refund_rate"
    assert result.dimensions[0].concept == "region"


@pytest.mark.asyncio
async def test_llm_parser_rejects_invalid_structured_output():
    client = AsyncMock()
    client.parse_analysis_intent.return_value = {
        "task_types": ["aggregation"],
        "overall_confidence": 1.5,
    }

    with pytest.raises(LLMResponseError, match="分析意图响应结构无效"):
        await AnalysisIntentLLMParser(client=client).parse("统计退款率")
