# 答案生成 Agent 模块
# 将 SQL 查询结果转换为用户易懂的自然语言解释
# 是 LangGraph pipeline 中的最后一个节点

from typing import Dict, Any

from ..services.llm_service import llm_client
from ..utils.logger import logger
from ..utils.exceptions import LLMError


class AnswerGenerator:
    """答案生成 Agent，负责查询结果 → 自然语言解释的转换"""

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
            answer = await llm_client.generate_answer(question, sql, query_result)

            logger.info("答案生成成功")
            return answer

        except Exception as e:
            logger.error(f"答案生成异常: {e}")
            raise LLMError(f"答案生成失败: {e}")


# 全局答案生成器实例
answer_generator = AnswerGenerator()
