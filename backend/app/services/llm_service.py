# LLM 服务模块
# 封装所有与 Qwen API (DashScope) 的交互，提供三个核心功能：
# 1. SQL 生成：根据自然语言问题和数据库 Schema 生成 SQL
# 2. SQL 修复：当 SQL 执行失败时，根据错误信息修复 SQL
# 3. 答案生成：根据查询结果生成自然语言解释

import json
import httpx
import logging
import time
from typing import Optional

from ..config import settings
from .llm_observability import calculate_estimated_cost, record_call
from ..utils.exceptions import LLMError, LLMTimeoutError, LLMResponseError

logger = logging.getLogger(__name__)

# 默认超时时间（秒），防止 API 请求无限等待
DEFAULT_TIMEOUT = 30

# SQL 生成和修复使用低温度，保证结果稳定可预测
SQL_TEMPERATURE = 0.1

# 答案生成使用稍高温度，让回答更自然流畅
ANSWER_TEMPERATURE = 0.3


class QwenAPIClient:
    """Qwen API 客户端，负责与 DashScope 文本生成服务通信"""

    def __init__(self):
        # 从配置中读取 API 密钥和端点，避免硬编码
        self.api_key = settings.QWEN_API_KEY
        self.api_url = settings.QWEN_API_URL
        self.model = settings.QWEN_MODEL

        # 最大重试次数，从配置读取，默认 3 次
        self.max_retries = settings.SQL_MAX_RETRIES

    def _build_headers(self) -> dict:
        """构建请求头，包含 API 认证信息"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _build_payload(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int = 2000
    ) -> dict:
        """构建请求体

        Args:
            messages: 对话消息列表，包含 system 和 user 角色
            temperature: 温度参数，越低结果越确定性
            max_tokens: 最大生成 token 数
        """
        return {
            "model": self.model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "result_format": "message",
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        }

    async def _call_api(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int = 2000,
        stage: str = "unknown",
    ) -> str:
        """调用 Qwen API 并返回响应内容

        实现指数退避重试机制：当 API 调用失败时，等待 2^attempt 秒后重试，
        避免在 API 限流时频繁请求导致问题恶化。

        Returns: API 返回的文本内容

        Raises:
            LLMTimeoutError: 请求超时
            LLMResponseError: 响应格式异常
            LLMError: 其他 API 错误
        """
        payload = self._build_payload(messages, temperature, max_tokens)
        headers = self._build_headers()
        started_at = time.perf_counter()

        # 指数退避重试循环
        for attempt in range(self.max_retries):
            attempt_count = attempt + 1
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                        timeout=DEFAULT_TIMEOUT
                    )

                    # 检查 HTTP 状态码
                    if response.status_code != 200:
                        raise LLMResponseError(
                            f"API 返回非 200 状态码: {response.status_code}, "
                            f"响应: {response.text}"
                        )

                    result = response.json()

                    # 从响应中提取生成的文本内容
                    # Qwen API 响应结构: output.choices[0].message.content
                    content = result["output"]["choices"][0]["message"]["content"]
                    self._record_observability(
                        stage=stage,
                        started_at=started_at,
                        attempt_count=attempt_count,
                        usage=result.get("usage"),
                        success=True,
                    )
                    return content

            except httpx.TimeoutException as exc:
                # 超时异常，记录日志并决定是否重试
                logger.warning(f"API 调用超时 (第 {attempt + 1} 次)")
                if attempt == self.max_retries - 1:
                    self._record_observability(
                        stage=stage,
                        started_at=started_at,
                        attempt_count=attempt_count,
                        success=False,
                        error_type=type(exc).__name__,
                    )
                    raise LLMTimeoutError(f"API 调用超时，已重试 {self.max_retries} 次")

            except (LLMResponseError, LLMError) as exc:
                # 响应异常或业务异常，直接抛出不重试
                self._record_observability(
                    stage=stage,
                    started_at=started_at,
                    attempt_count=attempt_count,
                    success=False,
                    error_type=type(exc).__name__,
                )
                raise

            except (KeyError, IndexError, TypeError) as exc:
                # 响应 JSON 结构异常（缺少字段、数组越界等），重试无意义，直接报错
                self._record_observability(
                    stage=stage,
                    started_at=started_at,
                    attempt_count=attempt_count,
                    success=False,
                    error_type=type(exc).__name__,
                )
                raise LLMResponseError(f"API 响应结构异常: {exc}")

            except Exception as e:
                # 其他异常，记录日志并决定是否重试
                logger.error(f"API 调用异常: {e} (第 {attempt + 1} 次)")
                if attempt == self.max_retries - 1:
                    self._record_observability(
                        stage=stage,
                        started_at=started_at,
                        attempt_count=attempt_count,
                        success=False,
                        error_type=type(e).__name__,
                    )
                    raise LLMError(f"API 调用失败: {e}")

            # 指数退避：第 1 次等 1 秒，第 2 次等 2 秒，第 3 次等 4 秒
            import asyncio
            await asyncio.sleep(2 ** attempt)

        raise LLMError("API 调用失败，已达最大重试次数")

    def _record_observability(
        self,
        stage: str,
        started_at: float,
        attempt_count: int,
        usage: Optional[dict] = None,
        success: bool = False,
        error_type: Optional[str] = None,
    ) -> None:
        """记录一次逻辑 LLM 调用；观测失败不得影响业务主流程。"""
        try:
            usage = usage or {}
            input_tokens = self._safe_token_count(usage.get("input_tokens"))
            output_tokens = self._safe_token_count(usage.get("output_tokens"))
            total_tokens = self._safe_token_count(usage.get("total_tokens"))
            if not total_tokens:
                total_tokens = input_tokens + output_tokens

            record_call(
                {
                    "stage": stage,
                    "model": self.model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "latency_ms": max(0, round((time.perf_counter() - started_at) * 1000)),
                    "attempt_count": attempt_count,
                    "estimated_cost": calculate_estimated_cost(
                        input_tokens,
                        output_tokens,
                        settings.QWEN_INPUT_PRICE_PER_MILLION_TOKENS,
                        settings.QWEN_OUTPUT_PRICE_PER_MILLION_TOKENS,
                    ),
                    "success": success,
                    "error_type": error_type,
                }
            )
        except Exception as exc:
            logger.warning(f"LLM 可观测性记录失败: {type(exc).__name__}")

    def _safe_token_count(self, value: object) -> int:
        """兼容 DashScope usage 缺失或异常字段，避免观测数据阻断成功调用。"""
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    async def generate_sql(
        self,
        question: str,
        schema_info: str,
        conversation_context: str = "",
        analysis_intent: str = "",
    ) -> dict:
        """根据自然语言问题和数据库 Schema 生成 SQL

        这是整个系统的核心功能：将用户的自然语言问题转换为可执行的 SQL 查询。

        Args:
            question: 用户的自然语言问题，例如"查询销售额最高的前 5 个商品"
            schema_info: 数据库 Schema 信息，包含表结构和字段说明
            conversation_context: 多轮追问上下文摘要；为空时按单轮问题处理
            analysis_intent: 分层意图解析结果的文本描述；为空时不注入

        Returns:
            dict: 包含 sql、tables、explanation 的结构化结果
        """
        # 系统提示词：告诉 LLM 它的角色和输出格式要求
        system_prompt = """你是一个专业的 SQL 生成助手。根据用户的自然语言问题和数据库 Schema，生成可执行的 SQL 查询。

要求：
1. 只生成 SELECT 或 WITH 查询语句，禁止生成 DDL/DML 语句
2. 使用 DuckDB 方言（注意：DuckDB 不支持 MySQL 的 LIMIT offset, count 语法）
3. 优先遵循业务语义层中的业务指标口径、维度定义、默认时间字段和 JOIN 关系
4. 如果用户问题命中业务指标或维度别名，必须使用语义层给出的表达式和关联关系
5. 业务指标必须使用语义层方括号中的稳定英文 key 作为输出别名；维度使用物理字段名作为输出别名，禁止使用中文别名或自创缩写
6. 如果语义层为当前维度声明了粒度覆盖表达式，必须使用覆盖表达式，避免 JOIN 后重复汇总
7. 如果用户是多轮追问并省略了指标、维度、时间范围或过滤条件，优先继承多轮对话上下文中最近一轮的分析意图
8. 返回严格的 JSON 格式，不要包含任何其他文本

输出格式：
{
    "sql": "生成的 SQL 查询语句",
    "tables": ["使用的表名列表"],
    "explanation": "SQL 逻辑的简要说明"
}"""

        # 用户提示词：包含 Schema 信息和用户问题
        context_section = ""
        if conversation_context:
            # 只有存在 session 上下文时才加入 prompt，避免单轮查询被无关历史干扰。
            context_section = f"""

多轮对话上下文：
{conversation_context}
"""

        intent_section = ""
        if analysis_intent:
            intent_section = f"""

{analysis_intent}
"""

        user_prompt = f"""数据库 Schema 与业务语义信息：
{schema_info}
{context_section}{intent_section}
用户问题：{question}

请根据以上信息生成 SQL 查询。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 调用 API 获取响应
        content = await self._call_api(messages, SQL_TEMPERATURE, stage="generate_sql")

        # 解析 JSON 响应
        return self._parse_json_response(content, "SQL 生成")

    async def parse_analysis_intent(
        self,
        question: str,
        semantic_summary: str,
    ) -> dict:
        """将复杂分析问题解析为结构化业务意图，不提前绑定物理 Schema。"""
        system_prompt = """你是数据分析意图解析器。请将用户问题转换为结构化业务意图。

要求：
1. 只表达任务类型、指标概念、维度概念、过滤条件、时间粒度、排序和缺失槽位
2. 使用业务语义摘要中的稳定英文 key 表达已知指标和维度
3. 对隐式、多意图或不确定表达保留合理置信度，不要猜测不存在的业务概念
4. 禁止输出 SQL
5. 禁止输出物理表名或物理字段名
6. 禁止输出内部推理过程
7. 返回严格 JSON，不要包含其他文本

输出格式：
{
  "task_types": ["aggregation"],
  "metrics": [{"concept": "sales_amount", "confidence": 0.9, "evidence": "销售额"}],
  "dimensions": [{"concept": "region", "confidence": 0.9, "evidence": "地区"}],
  "filters": [],
  "time_granularity": null,
  "ranking": null,
  "missing_slots": [],
  "conflicts": [],
  "overall_confidence": 0.9
}"""
        user_prompt = f"""业务语义摘要：
{semantic_summary}

用户问题：{question}

请输出结构化分析意图。"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content = await self._call_api(
            messages,
            SQL_TEMPERATURE,
            max_tokens=1600,
            stage="parse_analysis_intent",
        )
        return self._parse_json_response(content, "分析意图")

    async def repair_sql(
        self,
        original_sql: str,
        error_message: str,
        schema_info: str
    ) -> dict:
        """修复执行失败的 SQL

        当 SQL 执行出错时，将原始 SQL、错误信息和 Schema 一起发给 LLM，
        让它分析错误原因并生成修复后的 SQL。

        Args:
            original_sql: 原始的有问题的 SQL
            error_message: 数据库返回的错误信息
            schema_info: 数据库 Schema 信息

        Returns:
            dict: 包含 repaired_sql 和 repair_reason 的结构化结果
        """
        system_prompt = """你是一个 SQL 修复专家。根据原始 SQL、错误信息和数据库 Schema，分析错误原因并生成修复后的 SQL。

要求：
1. 只修复 SQL 语法和逻辑错误，不要改变查询意图
2. 只生成 SELECT 或 WITH 查询语句
3. 使用 DuckDB 方言
4. DuckDB 季度提取优先使用 EXTRACT(QUARTER FROM date_column)，不要使用不受支持的 strftime %q/%Q
5. strftime 等函数返回字符串；字符串参与算术前必须显式 CAST 为 INTEGER 或其他数值类型
6. 返回严格的 JSON 格式

输出格式：
{
    "repaired_sql": "修复后的 SQL 查询语句",
    "repair_reason": "错误原因和修复说明"
}"""

        user_prompt = f"""原始 SQL：
{original_sql}

错误信息：
{error_message}

数据库 Schema：
{schema_info}

请分析错误原因并生成修复后的 SQL。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        content = await self._call_api(messages, SQL_TEMPERATURE, stage="repair_sql")
        return self._parse_json_response(content, "SQL 修复")

    async def generate_answer(
        self,
        question: str,
        sql: str,
        query_result: dict
    ) -> str:
        """根据查询结果生成自然语言解释

        将技术性的 SQL 查询结果转换为用户易懂的自然语言回答。

        Args:
            question: 用户的原始问题
            sql: 执行的 SQL 查询
            query_result: 查询结果，包含 columns、rows 等信息

        Returns:
            str: 自然语言解释文本
        """
        system_prompt = """你是一个数据分析助手。根据用户的原始问题、执行的 SQL 查询和查询结果，生成简洁易懂的自然语言解释。

要求：
1. 用通俗易懂的语言解释查询结果
2. 突出关键数据和趋势
3. 如果结果为空，说明可能的原因
4. 不要重复 SQL 语句本身"""

        # 将查询结果格式化为易读的文本
        result_text = self._format_query_result(query_result)

        user_prompt = f"""用户问题：{question}

执行的 SQL：
{sql}

查询结果：
{result_text}

请根据以上信息生成自然语言解释。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 答案生成不需要 JSON 解析，直接返回文本
        content = await self._call_api(messages, ANSWER_TEMPERATURE, stage="generate_answer")
        return content

    def _parse_json_response(self, content: str, context: str) -> dict:
        """解析 LLM 返回的 JSON 响应

        LLM 返回的文本可能包含额外的说明文字，需要提取其中的 JSON 部分。

        Args:
            content: LLM 返回的原始文本
            context: 调用场景描述，用于错误信息

        Returns:
            dict: 解析后的 JSON 数据

        Raises:
            LLMResponseError: 无法解析 JSON 时抛出
        """
        try:
            # 尝试直接解析整个响应
            return json.loads(content)
        except json.JSONDecodeError:
            # 直接解析失败，尝试提取 JSON 部分
            # 有些 LLM 会在 JSON 前后添加说明文字
            try:
                # 查找 JSON 的开始和结束位置
                start = content.index('{')
                end = content.rindex('}') + 1
                json_str = content[start:end]
                return json.loads(json_str)
            except (ValueError, json.JSONDecodeError) as e:
                raise LLMResponseError(
                    f"{context}响应不是有效的 JSON: {content[:200]}..."
                )

    def _format_query_result(self, query_result: dict) -> str:
        """将查询结果格式化为易读的文本

        Args:
            query_result: 查询结果字典，包含 columns 和 rows

        Returns:
            str: 格式化后的文本
        """
        if not query_result.get("rows"):
            return "查询结果为空"

        columns = query_result.get("columns", [])
        rows = query_result.get("rows", [])

        # 构建表格形式的文本表示
        lines = []
        lines.append("列名: " + ", ".join(columns))
        lines.append(f"共 {len(rows)} 条记录")

        # 最多显示前 10 条记录，避免结果过长
        for i, row in enumerate(rows[:10]):
            lines.append(f"记录 {i + 1}: {row}")

        if len(rows) > 10:
            lines.append(f"... 还有 {len(rows) - 10} 条记录")

        return "\n".join(lines)


# 全局单例，整个应用共享同一个客户端实例
llm_client = QwenAPIClient()
