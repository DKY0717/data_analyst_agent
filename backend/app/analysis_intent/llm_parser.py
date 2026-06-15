"""使用 Qwen 补充复杂、多意图和隐式分析需求。"""

from pydantic import ValidationError

from .models import AnalysisIntent
from ..semantic.semantic_loader import semantic_loader
from ..services.llm_service import llm_client
from ..utils.exceptions import LLMResponseError


class AnalysisIntentLLMParser:
    """调用 LLM 后使用稳定契约校验输出，不信任未经验证的模型 JSON。"""

    def __init__(self, client=llm_client, semantic=semantic_loader):
        self.client = client
        self.semantic = semantic

    async def parse(self, question: str) -> AnalysisIntent:
        """解析复杂意图；API 调用异常由上层决定是否使用规则结果降级。"""
        payload = await self.client.parse_analysis_intent(
            question,
            self.semantic.format_for_prompt(),
        )
        try:
            return AnalysisIntent.model_validate(payload)
        except (ValidationError, TypeError) as exc:
            # 不传播模型原始响应，避免错误信息携带用户输入或不可控内容。
            raise LLMResponseError("分析意图响应结构无效") from exc
