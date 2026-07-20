# LLM 服务模块
# 封装 OpenAI-compatible LLM API 交互；QWEN_* 变量名仅为历史兼容，当前默认可接 MiMo/Qwen 等端点。
# 1. SQL 生成：根据自然语言问题和数据库 Schema 生成 SQL
# 2. SQL 修复：当 SQL 执行失败时，根据错误信息修复 SQL
# 3. 答案生成：根据查询结果生成自然语言解释

import asyncio
import json
import httpx
import logging
import re
import time
from typing import Optional

from ..config import settings
from .llm_observability import calculate_estimated_cost, record_call
from .prompt_registry import prompt_registry
from .ab_test import ab_test_registry
from ..utils.exceptions import LLMError, LLMTimeoutError, LLMResponseError

logger = logging.getLogger(__name__)

# 默认超时时间（秒），推理模型需要更长时间
DEFAULT_TIMEOUT = 120

# SQL 生成和修复使用低温度，保证结果稳定可预测
SQL_TEMPERATURE = 0.1

# 答案生成使用稍高温度，让回答更自然流畅
ANSWER_TEMPERATURE = 0.3

# 推理模型需要更多 tokens（reasoning + content）
DEFAULT_MAX_TOKENS = 8192


class QwenAPIClient:
    """LLM API 客户端，支持 OpenAI 兼容协议（MiMo、Qwen 等）"""

    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.api_url = settings.QWEN_API_URL
        self.model = settings.QWEN_MODEL
        self.max_retries = settings.SQL_MAX_RETRIES

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _build_payload(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> dict:
        """构建 OpenAI 兼容的请求体"""
        return {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

    async def _call_api(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int = DEFAULT_MAX_TOKENS,
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

        # 所有可重试结果共享同一总预算，避免某个分支绕过终止条件。
        for attempt in range(1, self.max_retries + 1):
            attempt_count = attempt
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                        timeout=DEFAULT_TIMEOUT
                    )

                    # 检查 HTTP 状态码
                    if response.status_code == 429:
                        provider_code, provider_type = self._provider_error_details(
                            response
                        )
                        error_metadata = self._format_provider_error_metadata(
                            provider_code, provider_type
                        )
                        if attempt >= self.max_retries:
                            raise LLMResponseError(
                                "API 限流 429，已达最大重试次数"
                                f"{error_metadata}",
                                status_code=429,
                                provider_code=provider_code,
                                provider_type=provider_type,
                            )
                        wait = min(4 * attempt, 60)
                        logger.warning(
                            "API 限流 429，等待 %ss 后重试 (第 %s/%s 次)",
                            wait,
                            attempt,
                            self.max_retries,
                        )
                        await asyncio.sleep(wait)
                        continue
                    if response.status_code != 200:
                        provider_code, provider_type = self._provider_error_details(
                            response
                        )
                        error_metadata = self._format_provider_error_metadata(
                            provider_code, provider_type
                        )
                        raise LLMResponseError(
                            "API 返回非 200 状态码: "
                            f"{response.status_code}{error_metadata}",
                            status_code=response.status_code,
                            provider_code=provider_code,
                            provider_type=provider_type,
                        )

                    result = response.json()

                    # OpenAI 兼容响应格式: choices[0].message.content
                    content = result["choices"][0]["message"]["content"]

                    # 推理模型可能消耗所有 tokens 在 reasoning 上，导致 content 为空
                    if not content or not content.strip():
                        reasoning = result["choices"][0]["message"].get("reasoning_content", "")
                        if reasoning:
                            logger.warning(f"推理模型返回空 content，reasoning 长度: {len(reasoning)}")
                            if attempt >= self.max_retries:
                                raise LLMResponseError(
                                    "推理模型连续返回空 content，已达最大重试次数"
                                )
                            # 在共享预算内重试，让模型有机会生成最终内容。
                            continue
                        raise LLMResponseError("API 返回空内容")

                    self._record_observability(
                        stage=stage,
                        started_at=started_at,
                        attempt_count=attempt_count,
                        usage=result.get("usage"),
                        success=True,
                    )
                    return content

            except httpx.TimeoutException as exc:
                logger.warning(f"API 调用超时 (第 {attempt} 次)")
                if attempt >= self.max_retries:
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
                raise LLMResponseError("API 响应结构异常") from exc

            except Exception as e:
                logger.error("API 调用异常: %s (第 %s 次)", type(e).__name__, attempt)
                if attempt >= self.max_retries:
                    self._record_observability(
                        stage=stage,
                        started_at=started_at,
                        attempt_count=attempt_count,
                        success=False,
                        error_type=type(e).__name__,
                    )
                    raise LLMError("API 调用失败") from e

            # 指数退避：第 1 次等 2 秒，第 2 次等 4 秒，以此类推。
            await asyncio.sleep(2 ** attempt)

        raise LLMError("API 调用失败，已达最大重试次数")

    @classmethod
    def _provider_error_details(
        cls, response: httpx.Response
    ) -> tuple[str | None, str | None]:
        """仅提取安全的错误码/类型，绝不传播可能回显输入数据的 message。"""
        try:
            payload = response.json()
        except (ValueError, TypeError):
            return None, None

        if not isinstance(payload, dict):
            return None, None
        error = payload.get("error")
        error_payload = error if isinstance(error, dict) else payload
        return (
            cls._sanitize_provider_error_token(error_payload.get("code")),
            cls._sanitize_provider_error_token(error_payload.get("type")),
        )

    @staticmethod
    def _format_provider_error_metadata(
        provider_code: str | None, provider_type: str | None
    ) -> str:
        """把已清洗的 provider 标识格式化到安全异常消息中。"""
        parts = []
        if provider_code:
            parts.append(f"code={provider_code}")
        if provider_type:
            parts.append(f"type={provider_type}")
        return f" ({', '.join(parts)})" if parts else ""

    @staticmethod
    def _sanitize_provider_error_token(value: object) -> str | None:
        """错误元数据只允许短标识符字符，防止供应商响应内容进入日志。"""
        if not isinstance(value, str):
            return None
        token = re.sub(r"[^A-Za-z0-9_.:-]", "", value)[:80]
        return token or None

    def _record_observability(
        self,
        stage: str,
        started_at: float,
        attempt_count: int,
        usage: Optional[dict] = None,
        success: bool = False,
        error_type: Optional[str] = None,
    ) -> None:
        """记录一次逻辑 LLM 调用；兼容 DashScope 和 OpenAI 两种 usage 格式。"""
        try:
            usage = usage or {}
            # 兼容两种格式: OpenAI (prompt_tokens/completion_tokens) 和 DashScope (input_tokens/output_tokens)
            input_tokens = self._safe_token_count(
                usage.get("prompt_tokens") or usage.get("input_tokens")
            )
            output_tokens = self._safe_token_count(
                usage.get("completion_tokens") or usage.get("output_tokens")
            )
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

        # 注册 prompt 版本（内容不变时不创建新版本）
        prompt_registry.register("generate_sql", system_prompt, "动态模板")

        # A/B 测试路由
        ab_variant = ab_test_registry.route("generate_sql", question)
        ab_test_id = None
        if ab_variant:
            ab_test_id = "generate_sql"
            # 如果有 A/B 测试，使用变体对应的 prompt 版本
            alt_prompt = prompt_registry.get_by_version(ab_variant.prompt_name, ab_variant.prompt_version)
            if alt_prompt:
                system_prompt = alt_prompt.system_prompt

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 调用 API 获取响应
        started_at = time.perf_counter()
        content = await self._call_api(messages, SQL_TEMPERATURE, stage="generate_sql")
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        # 记录 A/B 测试结果
        if ab_test_id and ab_variant:
            ab_test_registry.record(
                test_id=ab_test_id,
                variant_name=ab_variant.name,
                question=question,
                success=True,
                latency_ms=latency_ms,
            )

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
        schema_info: str,
        system_suffix: str = "",
        temperature: float | None = None,
    ) -> dict:
        """修复执行失败的 SQL（支持差异化策略）

        Args:
            original_sql: 原始的有问题的 SQL
            error_message: 数据库返回的错误信息
            schema_info: 数据库 Schema 信息
            system_suffix: 针对特定错误类型的修复策略提示
            temperature: 覆盖默认温度（列名修正用低温度，语法修复用稍高温度）
        """
        base_prompt = """你是一个 SQL 修复专家。根据原始 SQL、错误信息和数据库 Schema，分析错误原因并生成修复后的 SQL。

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

        system_prompt = base_prompt + (system_suffix or "")

        user_prompt = f"""原始 SQL：
{original_sql}

错误信息：
{error_message}

数据库 Schema：
{schema_info}

请分析错误原因并生成修复后的 SQL。"""

        prompt_registry.register("repair_sql", base_prompt, "动态模板")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        call_temperature = temperature if temperature is not None else SQL_TEMPERATURE
        content = await self._call_api(messages, call_temperature, stage="repair_sql")
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

        prompt_registry.register("generate_answer", system_prompt, "动态模板")

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
            except (ValueError, json.JSONDecodeError):
                raise LLMResponseError(f"{context}响应不是有效的 JSON")

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
