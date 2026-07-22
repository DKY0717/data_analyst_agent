# 答案生成 Agent 模块
# 将 SQL 查询结果转换为用户易懂的自然语言解释
# 是 LangGraph pipeline 中的最后一个节点

from typing import Dict, Any

from ..services.llm_service import llm_client
from ..utils.logger import logger
from ..utils.exceptions import LLMError


class AnswerGenerator:
    """答案生成 Agent，负责查询结果 → 自然语言解释的转换"""

    def __init__(self, client=None):
        # 评测可替换外部模型，业务编排和结果处理仍走真实 Agent 节点。
        self._client = client

    @property
    def client(self):
        """未注入时动态读取全局 client，方便测试替换且不改变生产默认。"""
        return self._client or llm_client

    async def generate(
        self,
        question: str,
        sql: str,
        query_result: Dict[str, Any]
    ) -> str:
        """
        根据查询结果生成自然语言解释

        Args:
            question: 用户的原始问题
            sql: 执行的 SQL 查询
            query_result: 查询结果，来自 QueryRunner.execute()

        Returns:
            str: 自然语言解释文本

        Raises:
            LLMError: LLM 调用失败时抛出
        """
        try:
            # 调用 LLM 生成答案，返回纯文本
            answer = await self.client.generate_answer(question, sql, query_result)

            logger.info("答案生成成功")
            return answer

        except Exception as e:
            logger.error("答案生成异常: %s", type(e).__name__)
            raise LLMError("答案生成失败") from e


# 全局答案生成器实例
answer_generator = AnswerGenerator()
