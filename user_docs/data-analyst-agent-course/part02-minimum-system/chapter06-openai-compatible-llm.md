# 第六章 接入 OpenAI-compatible 大模型

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 6.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 理解 OpenAI-compatible API 的请求和响应结构；
> 2. 说明项目为什么保留 `QWEN_*` 配置名但不把客户端绑定到单一供应商；
> 3. 读懂 `_build_headers()`、`_build_payload()` 和 `_call_api()`；
> 4. 区分超时、限流、响应格式错误和业务异常；
> 5. 理解 SQL 生成与答案生成为什么使用不同温度；
> 6. 使用 Mock 测试验证 LLM 调用，而不消耗真实额度。

## 6.2 问题场景

> SQL Generator、SQL Repair 和 Answer Generator 都需要调用模型。如果每个模块都自己拼 URL、请求头和重试逻辑，系统会出现重复代码、错误处理不一致和密钥泄露风险。
>
> `backend/app/services/llm_service.py` 把这些共性集中到 `QwenAPIClient`。名称保留了历史兼容性，但它调用的是 OpenAI-compatible 的 HTTP 协议：只要服务端接受相同的 `model`、`messages`、`temperature` 和 `max_tokens` 字段，就可以更换供应商或模型。

## 6.3 OpenAI-compatible 请求结构

```json
{
  "model": "mimo-v2.5-pro",
  "messages": [
    {"role": "system", "content": "你是 SQL 生成助手"},
    {"role": "user", "content": "统计本月销售额"}
  ],
  "temperature": 0.1,
  "max_tokens": 8192
}
```

> `messages` 用角色区分系统约束和用户问题；`temperature` 控制输出随机性；`max_tokens` 限制输出长度。项目的 SQL 任务要求稳定、可解析，所以使用较低温度；自然语言答案可以稍微自然一些，使用更高温度。

## 6.4 配置和密钥边界

```python
class QwenAPIClient:
    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.api_url = settings.QWEN_API_URL
        self.model = settings.QWEN_MODEL
        self.max_retries = settings.SQL_MAX_RETRIES
```

> 客户端从 `Settings` 读取配置，而不是在业务函数里直接调用 `os.getenv()`。这样测试可以替换 Settings 或注入 Fake Client，生产环境也可以通过环境变量改变模型端点。

> `Authorization` 请求头只在内存中构造并发送，不能写入日志、异常响应或审计报告。`.env` 应加入 Git 忽略规则，`.env.example` 只能包含变量名和示例值。

## 6.5 请求构造

```python
def _build_headers(self) -> dict:
    return {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json",
    }

def _build_payload(self, messages, temperature, max_tokens=DEFAULT_MAX_TOKENS):
    return {
        "model": self.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
```

> 把请求构造拆出来有两个好处：一是业务方法只关心 Prompt 和结果，二是可以对请求体做单元测试而不发出网络请求。注意，测试请求体时可以检查模型、消息和温度，但不能把真实 API Key 写入测试固件。

## 6.6 `_call_api()` 的重试策略

> 当前实现把错误分成几类：

| 情况 | 当前行为 | 原因 |
|---|---|---|
| HTTP 429 | 单独等待后重试，最多 8 次限流重试 | 服务端临时限流，重试可能恢复 |
| 超时 | 最多按配置重试，耗尽后抛出 `LLMTimeoutError` | 网络或模型响应过慢 |
| 非 200 响应 | 记录失败并抛出 `LLMResponseError` | 需要先确认服务端错误 |
| JSON 缺少 `choices` | 直接抛出响应格式错误 | 重试不能修复协议不匹配 |
| 其他异常 | 指数退避后重试，耗尽后抛出 `LLMError` | 处理临时网络异常 |

```text
第 1 次失败 → 等待 2 秒
第 2 次失败 → 等待 4 秒
第 3 次失败 → 等待 8 秒
```

> 重试不是“无限再试”。每次失败都会增加延迟和成本，尤其是模型调用。SQL Repair 还有自己的业务重试次数；网络重试和 SQL 业务修复是两层不同的机制，不能混为一谈。

## 6.7 解析响应和推理模型兼容

```python
result = response.json()
content = result["choices"][0]["message"]["content"]

if not content or not content.strip():
    reasoning = result["choices"][0]["message"].get("reasoning_content", "")
    if reasoning:
        continue
    raise LLMResponseError("API 返回空内容")
```

> OpenAI-compatible 响应通常从 `choices[0].message.content` 读取正文。某些推理模型可能把输出预算消耗在 `reasoning_content`，导致正文为空；项目会让请求重试，而不是把空字符串交给 JSON 解析器。

> 这不是对所有模型协议的保证。接入新供应商时，应先用最小请求确认它的字段和错误格式，再决定是否加入客户端兼容逻辑。

## 6.8 结构化输出的边界

> `generate_sql()` 要求模型返回 JSON，但“在 Prompt 中要求 JSON”并不等于模型一定会返回合法 JSON。服务端先拿到文本，再由 `_parse_json_response()` 解析并校验必要字段；缺少 `sql` 或格式错误时会抛出 `LLMError`，而不是让下游执行半成品。

```json
{
  "sql": "SELECT ...",
  "tables": ["orders"],
  "explanation": "按月份汇总订单金额"
}
```

> 结构化输出解决的是接口可读性，不解决 SQL 安全性。即使 JSON 格式正确，里面的 SQL 仍然必须经过后续 Guard。

## 6.9 Prompt 注册和可观测性

> SQL 生成会调用 `prompt_registry.register("generate_sql", ...)`。注册表把 Prompt 名称、版本号、哈希和时间保存到 SQLite；相同内容不会重复创建版本。这样修改 Prompt 后可以知道使用的是哪一版，也可以按版本回滚。

> LLM 调用通过 `ContextVar` 保存请求级轨迹，记录阶段、模型、Token、耗时、重试次数、成功状态和可选成本。它不保存 Prompt、API Key 或完整响应。成本价格未配置时，成本字段保持 `null`，而不是伪造一个金额。

## 6.10 SQL 与答案生成的温度选择

| 任务 | 常量 | 目的 |
|---|---:|---|
| SQL 生成和修复 | `0.1` | 减少随机性，便于安全校验和回归 |
| 答案生成 | `0.3` | 允许解释更自然，但仍保持可控 |

> 温度不是可靠性的唯一来源。SQL 可靠性还依赖 Schema、语义层、结构化解析、AST Guard、执行反馈和评测。把温度调到 0 也不能替代这些确定性保护。

## 6.11 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/services/llm_service.py` | OpenAI-compatible 客户端 | 请求、重试、响应解析、三类模型任务 |
| `backend/app/config.py` | LLM 配置 | URL、模型、密钥、成本单价 |
| `backend/app/services/prompt_registry.py` | Prompt 版本注册 | 哈希、版本、回滚 |
| `backend/app/services/llm_observability.py` | 调用指标轨迹 | ContextVar、汇总、隐私边界 |
| `backend/tests/test_llm_service.py` | 客户端测试 | Mock 响应、异常、重试和 JSON |

## 6.12 动手验证

> 先运行不需要真实网络的测试：

```bash
pytest backend/tests/test_llm_service.py -q
```

> 若要手工检查请求格式，可以在测试中注入 Mock HTTP 客户端，确认请求体包含 `model`、`messages`、`temperature` 和 `max_tokens`。不要为了验证结构而使用真实 Key。

> 配置真实模型时，先确认以下变量存在，再执行一个单独的 API smoke test；真实调用可能产生费用，且网络失败不能归因于 SQL 代码：

```text
QWEN_API_KEY=...
QWEN_API_URL=...
QWEN_MODEL=...
```

## 6.13 常见错误

### `401` 或 `403`

> 通常是 Key 无效、端点不接受当前 Key，或请求头格式不符合服务商要求。不要把 Key 粘贴进代码；检查环境变量是否被当前启动进程读取。

### `429`

> 这是限流，不一定表示 Prompt 错误。客户端会执行限流重试，但如果持续失败，应减少并发、检查配额或更换可用端点。

### 返回不是 `choices[0].message.content`

> 说明服务端不完全兼容当前协议，或者实际返回了错误 JSON。先记录状态码和稳定的错误类型，不要直接把完整响应写进公开日志。

### JSON 解析失败

> 模型可能输出了 Markdown 代码围栏、解释文字或缺字段。先检查 `_parse_json_response()` 的行为，再在 Prompt 中加强格式要求；即使修复了解析，也不能跳过 SQL Guard。

## 6.14 本章小结

> LLM 服务层解决的是“如何安全、稳定地与模型通信”，而不是“如何相信模型”。请求构造、重试、响应解析、Prompt 版本和调用观测都应该集中管理；模型返回的 SQL 或答案仍然需要分别经过结构校验、业务流程和安全边界。

## 6.15 练习

1. 写一个 Mock 响应，模拟 `choices` 缺失，观察客户端抛出的异常类型。
2. 解释为什么 HTTP 429 和 SQL 执行失败不应该共用同一个重试计数。
3. 在本地 Prompt 注册表中注册两版不同 Prompt，查看版本号和哈希变化。
4. 说明为什么成本单价缺失时应返回 `null`，而不是把成本估算为 0。

## 6.16 下一章衔接

> 现在我们已经能调用模型并得到结构化文本，但还没有把数据库 Schema、用户问题、执行器和答案生成器串起来。下一章会先实现一条“有意保持简单”的最小 NL2SQL 链路，并明确它在加入安全层之前有哪些风险。
