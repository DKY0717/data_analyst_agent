# LLM 服务封装（Qwen API）

## 1. 学习目标

> - 理解如何通过 HTTP 调用大模型 API
> - 了解 prompt 工程的基本思路
> - 理解指数退避重试机制
> - 了解温度参数对生成结果的影响

## 2. LLM 在系统中的角色

> 大模型（Qwen/通义千问）在系统中承担三个任务：
>
> 1. **生成 SQL**：根据用户问题和数据库结构，生成可执行的 SQL 查询
> 2. **修复 SQL**：当 SQL 执行失败时，根据错误信息修复 SQL
> 3. **生成答案**：将 SQL 查询结果转换为用户易懂的自然语言解释

## 3. Qwen API 客户端

> 代码在 `backend/app/services/llm_service.py`。

### 3.1 客户端初始化

```python
class QwenAPIClient:
    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.api_url = settings.QWEN_API_URL   # DashScope API 端点
        self.model = settings.QWEN_MODEL        # 默认 qwen-turbo
        self.max_retries = settings.SQL_MAX_RETRIES  # 最大重试 3 次
```

> API 端点是阿里云 DashScope 的文本生成服务地址。所有配置都从环境变量读取，不硬编码。

### 3.2 请求构建

```python
def _build_headers(self) -> dict:
    return {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json"
    }

def _build_payload(self, messages, temperature, max_tokens=2000) -> dict:
    return {
        "model": self.model,
        "input": {
            "messages": messages  # 包含 system 和 user 角色的消息列表
        },
        "parameters": {
            "result_format": "message",
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    }
```

> **messages 格式说明：**
>
> `messages` 是一个列表，每个元素是 `{"role": "角色", "content": "内容"}`：
> - `system`：系统提示词，告诉 LLM 它的角色和输出格式
> - `user`：用户输入，包含问题和上下文信息

## 4. 三个核心功能

### 4.1 SQL 生成（generate_sql）

> 这是系统最核心的功能：将自然语言转换为 SQL。

```python
async def generate_sql(self, question, schema_info, conversation_context="", analysis_intent=""):
    system_prompt = """你是一个专业的 SQL 生成助手。

要求：
1. 只生成 SELECT 或 WITH 查询语句，禁止生成 DDL/DML 语句
2. 使用 DuckDB 方言
3. 返回严格的 JSON 格式

输出格式：
{
    "sql": "生成的 SQL 查询语句",
    "tables": ["使用的表名列表"],
    "explanation": "SQL 逻辑的简要说明"
}"""

    user_prompt = f"""数据库 Schema 与业务语义信息：
{schema_info}

用户问题：{question}

请根据以上信息生成 SQL 查询。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    content = await self._call_api(messages, SQL_TEMPERATURE)
    return self._parse_json_response(content)
```

> **prompt 设计要点：**
>
> 1. **System prompt** 定义角色和输出格式，LLM 会严格遵循
> 2. **User prompt** 包含具体的数据（Schema + 问题）
> 3. 要求返回 JSON 格式，方便程序解析
> 4. 明确禁止 DDL/DML 语句，增加安全约束

### 4.2 SQL 修复（repair_sql）

> 当 SQL 执行失败时，把原始 SQL、错误信息和 Schema 一起发给 LLM，让它修复。

```python
async def repair_sql(self, original_sql, error_message, schema_info):
    system_prompt = """你是一个 SQL 修复专家。

要求：
1. 只修复 SQL 语法和逻辑错误，不要改变查询意图
2. 使用 DuckDB 方言
3. 返回严格的 JSON 格式

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
```

> **修复场景示例：**
>
> 原始 SQL：`SELECT DATE_FORMAT(order_date, '%Y-%m') FROM orders`
> 错误信息：`Catalog Error: Function date_format does not exist`
> 修复后：`SELECT STRFTIME(order_date, '%Y-%m') FROM orders`
>
> 因为 DuckDB 用 `STRFTIME` 而不是 MySQL 的 `DATE_FORMAT`。

### 4.3 答案生成（generate_answer）

> 将查询结果转换为自然语言解释。

```python
async def generate_answer(self, question, sql, query_result):
    system_prompt = """你是一个数据分析助手。

要求：
1. 用通俗易懂的语言解释查询结果
2. 突出关键数据和趋势
3. 如果结果为空，说明可能的原因
4. 不要重复 SQL 语句本身"""

    user_prompt = f"""用户问题：{question}
执行的 SQL：{sql}
查询结果：{formatted_result}

请根据以上信息生成自然语言解释。"""
```

## 5. API 调用与重试机制

### 5.1 核心调用方法

```python
async def _call_api(self, messages, temperature, max_tokens=2000, stage="unknown"):
    payload = self._build_payload(messages, temperature, max_tokens)
    headers = self._build_headers()

    for attempt in range(self.max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=DEFAULT_TIMEOUT  # 30 秒超时
                )

                if response.status_code != 200:
                    raise LLMResponseError(...)

                result = response.json()
                content = result["output"]["choices"][0]["message"]["content"]
                return content

        except httpx.TimeoutException:
            if attempt == self.max_retries - 1:
                raise LLMTimeoutError(...)

        # 指数退避：等 1s, 2s, 4s 后重试
        await asyncio.sleep(2 ** attempt)

    raise LLMError("API 调用失败，已达最大重试次数")
```

### 5.2 指数退避（Exponential Backoff）

> 当 API 调用失败时，不是立即重试，而是等待越来越长的时间：
>
> - 第 1 次失败：等 1 秒后重试
> - 第 2 次失败：等 2 秒后重试
> - 第 3 次失败：等 4 秒后重试
>
> **为什么？**
>
> 如果 API 服务器因为过载而拒绝请求，立即重试会加重服务器负担。指数退避给服务器恢复的时间。这是分布式系统中的标准做法。

### 5.3 JSON 响应解析

> LLM 返回的文本可能不完全是 JSON，可能包含额外说明文字。解析器会尝试提取 JSON 部分：

```python
def _parse_json_response(self, content: str, context: str) -> dict:
    try:
        # 先尝试直接解析
        return json.loads(content)
    except json.JSONDecodeError:
        # 直接解析失败，提取 { ... } 部分
        start = content.index('{')
        end = content.rindex('}') + 1
        json_str = content[start:end]
        return json.loads(json_str)
```

## 6. 温度参数

> 温度（temperature）控制生成结果的随机性：

| 任务 | 温度值 | 原因 |
|------|--------|------|
| SQL 生成 | 0.1 | 需要精确、稳定、可预测 |
| SQL 修复 | 0.1 | 同上 |
| 答案生成 | 0.3 | 稍高一点，让回答更自然 |

> - `temperature = 0`：完全确定性，每次结果一样
> - `temperature = 1`：高随机性，每次结果可能不同
> - SQL 生成用低温度是为了减少"幻觉"（生成不存在的表名或列名）

## 7. Prompt 工程要点

> 系统的 prompt 设计遵循几个原则：
>
> 1. **角色明确**：告诉 LLM 它是"SQL 生成助手"还是"SQL 修复专家"
> 2. **格式约束**：明确要求返回 JSON，指定字段名
> 3. **限制范围**：只允许 SELECT，禁止 DDL/DML
> 4. **提供上下文**：把数据库 Schema 注入 prompt，让 LLM 知道有哪些表和列
> 5. **方言指定**：明确使用 DuckDB 方言，避免生成 MySQL/PostgreSQL 语法

## 8. 错误处理

> LLM 调用可能遇到的错误：

| 错误类型 | 处理方式 |
|----------|----------|
| 超时（30秒） | 指数退避重试，最多 3 次 |
| HTTP 非 200 | 直接抛出异常，不重试 |
| JSON 解析失败 | 尝试提取 JSON 部分，仍失败则报错 |
| 响应结构异常 | 直接抛出异常，不重试 |
| 网络异常 | 指数退避重试，最多 3 次 |

> **重试策略：** 只对超时和网络异常重试，对业务错误（如 JSON 解析失败）不重试，因为重试也不会改善结果。

## 9. 下一步

> LLM 服务理解后，接下来学习：
>
> - **Agent 工作流（LangGraph）** — 了解如何把所有步骤串联成完整的工作流
