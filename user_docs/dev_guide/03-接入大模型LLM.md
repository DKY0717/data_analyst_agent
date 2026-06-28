# 第三章：接入大模型（LLM）

> 本章目标：封装 Qwen API 调用，让系统能理解自然语言并生成 SQL。
>
> 完成本章后，你将能通过代码调用大模型，把自然语言问题转换为 SQL。

## 3.1 什么是 LLM API

> LLM（大语言模型）就是一个"超级聪明的文本生成器"。你给它一段文字（prompt），它返回一段回复。
>
> 调用 LLM 的方式是发 HTTP 请求，类似你在浏览器访问网页，只不过：
> - 浏览器发 GET 请求，服务器返回 HTML
> - 你发 POST 请求给 LLM API，它返回生成的文本
>
> 我们用阿里云的**通义千问（Qwen）**，通过 DashScope API 调用。

## 3.2 获取 API Key

> 1. 注册阿里云账号：https://www.aliyun.com/
> 2. 进入 DashScope 控制台：https://dashscope.console.aliyun.com/
> 3. 创建 API Key
>
> 把 Key 填入项目根目录的 `.env` 文件。用编辑器打开 `.env`，在文件末尾**追加**以下两行：

```text
QWEN_API_KEY=your_api_key_here
QWEN_MODEL=qwen-turbo
```

> **注意：** API Key 是敏感信息，绝对不要提交到 Git。

## 3.3 安装 HTTP 客户端

> 我们用 `httpx` 库发 HTTP 请求（比 Python 自带的 `requests` 更现代，支持异步）。

```bash
cd backend
pip install httpx==0.25.2
```

> 更新 `backend/requirements.txt`，**用以下内容替换整个文件**：

```text
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.2
python-dotenv==1.0.0
duckdb==0.9.2
httpx==0.25.2
```

## 3.4 更新配置

> 在 `backend/app/config.py` 的 `Settings` 类中加入 LLM 配置。找到 `SQL_MAX_RETRIES` 那一行，在它**下面**加入以下 3 行：

```python
    SQL_MAX_RETRIES: int = _get_int("SQL_MAX_RETRIES", 3)

    # Qwen API 配置（新增这 3 行）
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_API_URL: str = os.getenv(
        "QWEN_API_URL",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    )
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-turbo")
```

> **怎么找到插入位置？** 用 VS Code 打开 `backend/app/config.py`，按 `Ctrl+F` 搜索 `SQL_MAX_RETRIES`，在它下面粘贴即可。

## 3.5 编写 LLM 服务

> 创建 `backend/app/services/` 目录和 `__init__.py`：

```bash
mkdir backend/app/services
New-Item -Path "backend/app/services/__init__.py" -ItemType File -Force
```

> 创建 `backend/app/services/llm_service.py`：

```python
import json
import httpx
import asyncio
import logging
from ..config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
SQL_TEMPERATURE = 0.1       # SQL 生成用低温度，结果更稳定
ANSWER_TEMPERATURE = 0.3    # 答案生成用稍高温度，更自然


class QwenAPIClient:
    """Qwen API 客户端"""

    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.api_url = settings.QWEN_API_URL
        self.model = settings.QWEN_MODEL

    def _build_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _build_payload(self, messages, temperature, max_tokens=2000):
        return {
            "model": self.model,
            "input": {"messages": messages},
            "parameters": {
                "result_format": "message",
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        }

    async def _call_api(self, messages, temperature, max_tokens=2000):
        """调用 Qwen API，带指数退避重试"""
        payload = self._build_payload(messages, temperature, max_tokens)
        headers = self._build_headers()

        for attempt in range(3):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                        timeout=DEFAULT_TIMEOUT
                    )

                    if response.status_code != 200:
                        raise Exception(f"API 返回错误: {response.status_code}")

                    result = response.json()
                    # Qwen API 响应结构: output.choices[0].message.content
                    return result["output"]["choices"][0]["message"]["content"]

            except httpx.TimeoutException:
                logger.warning(f"API 超时 (第 {attempt + 1} 次)")
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)  # 等 1s, 2s, 4s

            except Exception as e:
                logger.error(f"API 调用异常: {e}")
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise Exception("API 调用失败")

    def _parse_json_response(self, content):
        """解析 LLM 返回的 JSON（可能包含额外文字）"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 { ... } 部分
            start = content.index('{')
            end = content.rindex('}') + 1
            return json.loads(content[start:end])

    async def generate_sql(self, question, schema_info):
        """根据问题和 Schema 生成 SQL

        Args:
            question: 用户的自然语言问题
            schema_info: 数据库表结构信息

        Returns:
            dict: {"sql": "...", "tables": [...], "explanation": "..."}
        """
        system_prompt = """你是一个专业的 SQL 生成助手。根据用户的自然语言问题和数据库 Schema，生成可执行的 SQL 查询。

要求：
1. 只生成 SELECT 查询语句，禁止生成 DDL/DML 语句
2. 使用 DuckDB 方言
3. 返回严格的 JSON 格式，不要包含任何其他文本

输出格式：
{
    "sql": "生成的 SQL 查询语句",
    "tables": ["使用的表名列表"],
    "explanation": "SQL 逻辑的简要说明"
}"""

        user_prompt = f"""数据库 Schema：
{schema_info}

用户问题：{question}

请根据以上信息生成 SQL 查询。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        content = await self._call_api(messages, SQL_TEMPERATURE)
        return self._parse_json_response(content)

    async def generate_answer(self, question, sql, query_result):
        """根据查询结果生成自然语言解释"""
        system_prompt = """你是一个数据分析助手。根据用户的原始问题、执行的 SQL 和查询结果，生成简洁易懂的自然语言解释。

要求：
1. 用通俗易懂的语言解释结果
2. 突出关键数据
3. 不要重复 SQL 语句"""

        # 格式化查询结果
        if not query_result.get("rows"):
            result_text = "查询结果为空"
        else:
            lines = [f"列名: {', '.join(query_result['columns'])}"]
            for i, row in enumerate(query_result["rows"][:10]):
                lines.append(f"记录 {i+1}: {row}")
            result_text = "\n".join(lines)

        user_prompt = f"""用户问题：{question}
执行的 SQL：{sql}
查询结果：
{result_text}

请生成自然语言解释。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return await self._call_api(messages, ANSWER_TEMPERATURE)

    async def repair_sql(self, original_sql, error_message, schema_info):
        """修复执行失败的 SQL

        Args:
            original_sql: 原始的有问题的 SQL
            error_message: 数据库返回的错误信息
            schema_info: 数据库 Schema 信息

        Returns:
            dict: {"repaired_sql": "...", "repair_reason": "..."}
        """
        system_prompt = """你是一个 SQL 修复专家。根据原始 SQL、错误信息和数据库 Schema，分析错误原因并生成修复后的 SQL。

要求：
1. 只修复 SQL 语法和逻辑错误，不要改变查询意图
2. 只生成 SELECT 查询语句
3. 使用 DuckDB 方言
4. 返回严格的 JSON 格式

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

        content = await self._call_api(messages, SQL_TEMPERATURE)
        return self._parse_json_response(content)


# 全局单例
llm_client = QwenAPIClient()
```

> **核心概念解释：**
>
> **messages 格式：** LLM API 接受一个消息列表，每条消息有 `role` 和 `content`：
> - `system`：系统提示词，告诉 LLM 它的角色和规则
> - `user`：用户输入
>
> **temperature（温度）：** 控制生成结果的随机性。0 = 完全确定，1 = 高随机性。SQL 生成用 0.1 是为了结果稳定。
>
> **指数退避：** 超时重试时等待时间翻倍（1s → 2s → 4s），给服务器恢复时间。

## 3.6 测试 LLM 调用

> 创建一个测试脚本来验证 LLM 调用是否正常。创建 `backend/test_llm.py`：

```python
import asyncio
import sys
sys.path.insert(0, ".")

from app.services.llm_service import llm_client
from app.db.schema_loader import schema_loader


async def test():
    # 获取 Schema
    schema = schema_loader.get_full_schema()

    # 测试 SQL 生成
    question = "查询销售额最高的前5个商品"
    print(f"问题: {question}")
    print(f"正在调用 LLM...")

    result = await llm_client.generate_sql(question, str(schema))
    print(f"生成的 SQL: {result['sql']}")
    print(f"使用的表: {result['tables']}")
    print(f"说明: {result['explanation']}")


asyncio.run(test())
```

> 运行测试：

```bash
cd backend
python test_llm.py
```

> 你应该看到类似输出：

```text
问题: 查询销售额最高的前5个商品
正在调用 LLM...
生成的 SQL: SELECT p.product_name, SUM(oi.quantity * oi.unit_price) AS total_sales FROM order_items oi JOIN products p ON oi.product_id = p.product_id GROUP BY p.product_name ORDER BY total_sales DESC LIMIT 5
使用的表: ['order_items', 'products']
说明: 通过订单明细表和商品表关联，按商品名称汇总销售额，降序排列取前5
```

> **如果报错：**
> - `QWEN_API_KEY is not set`：检查 `.env` 文件中的 Key 是否正确
> - `API 返回错误: 401`：API Key 无效
> - `API 返回错误: 429`：调用频率超限，等一会再试

## 3.7 项目目录现状

```text
data_analyst_agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py               # 加入了 Qwen API 配置
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py
│   │   │   └── schema_loader.py
│   │   └── services/
│   │       ├── __init__.py
│   │       └── llm_service.py      # 新增：LLM 服务封装
│   ├── test_llm.py                 # 新增：测试脚本
│   └── requirements.txt
├── database/
│   ├── init.sql
│   └── seed_data.py
├── .env
└── .gitignore
```

## 3.8 本章小结

> 你完成了：
> - 理解了 LLM API 的工作原理（发 HTTP 请求，收文本回复）
> - 编写了 Qwen API 客户端
> - 实现了 SQL 生成功能：自然语言 → SQL
> - 实现了答案生成功能：查询结果 → 自然语言
> - 测试验证了 LLM 调用正常工作
>
> 下一章我们将加入 SQL 安全防护，防止危险 SQL 被执行。
