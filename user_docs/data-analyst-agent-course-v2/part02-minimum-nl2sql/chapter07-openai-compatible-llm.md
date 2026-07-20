# 第7章 OpenAI-compatible LLM 客户端

> 本章预计 1～2 小时，优先使用 Fake/Mock 学习，不要求真实 API Key，也不会产生模型费用。

## 7.1 学习目标
> 能解释 OpenAI-compatible 请求、逻辑调用与 HTTP 尝试、结构化 JSON、异常分类、空 content、超时重试和脱敏观测。

## 7.2 前置知识
> 需要理解 JSON、异步 HTTP 和异常处理。

## 7.3 为什么需要这一模块
> 外部模型具有网络、认证、限流、格式漂移和长尾延迟风险，不能让每个 Agent 节点自行处理这些细节。

## 7.4 输入、输出与依赖
> 输入是 system/user 消息与任务参数；输出是 SQL/Intent/Repair 的字典或答案文本；依赖 endpoint、model、API Key 和异步 HTTP 客户端。调用边界只暴露清洗后的 `LLMError`，供应商细节作为脱敏元数据记录。

## 7.5 执行流程
```text
logical call → build headers/payload → HTTP attempt
  → status/error classification → choice.message.content
  → JSON parse or text → observability record
```

## 7.6 当前代码地图
| 内容 | 路径 |
|---|---|
| LLM 服务 | `backend/app/services/llm_service.py` |
| Prompt | `backend/app/services/prompt_registry.py` |
| 配置 | `backend/app/config.py` |
| 观测 | `backend/app/services/llm_observability.py` |
| 测试 | `backend/tests/test_llm_service.py` |

## 7.7 关键代码理解
### 7.7.1 兼容协议不等于行为完全一致

> 客户端发送 `model`、`messages` 等兼容字段，但不同供应商对 reasoning、content、JSON 模式、错误体和超时的行为仍可能不同。`QWEN_*` 变量名只是历史兼容层。

### 7.7.2 结构化输出必须解析和校验

```json
{"sql":"SELECT ...","tables":["orders"],"explanation":"..."}
```

> 模型输出仍是不可信文本。客户端先提取 content，再去除可接受围栏并解析 JSON；上层 `SQLGeneratorOutput` 继续校验必要字段。解析失败不能回退为随意执行原字符串。

### 7.7.3 重试有明确边界

> 超时、部分 429/5xx 或网络瞬断可重试；认证失败、请求格式错误和确定性解析错误不应无限重试。一次业务 `generate_sql()` 可能包含多次 HTTP attempt，审计必须区分二者。

### 7.7.4 content 为空是失败证据

> 某些 MiMo 响应出现 reasoning 有值但 content 为空。reasoning 不能当成业务答案或 JSON；客户端应按兼容性错误处理并记录尝试，而不是假装成功。长时间重复这类响应会放大尾延迟。

### 7.7.5 最小化观测

> 可记录 stage、model、token、耗时、attempt_count、成功和错误类型；不得记录 API Key、Authorization、完整 Prompt、原始业务行或完整供应商响应。

## 7.8 最小动手运行
```bash
pytest backend/tests/test_llm_service.py -q
```
> 工作目录：项目根目录。测试使用确定性响应，不访问外部模型。

## 7.9 故障注入实验
> 使用 Mock 依次返回超时、429、非法 JSON、reasoning 非空但 content 为空，记录哪些会重试、HTTP 尝试数和最终错误类型。恢复方式是移除替身，不改全局密钥。

## 7.10 调试路径与常见误判
> 先区分 DNS/连接、401、429、5xx、响应结构、空 content、JSON 解析和 Pydantic 校验。reasoning 非空不代表 content 可用；API Key 错误也不会通过改 Prompt 修好。

## 7.11 独立编码练习
> 为练习客户端定义 `complete_json(messages) -> dict`，注入 transport，最多两次尝试；为超时后成功、401 不重试、空 content 和非法 JSON 写测试，并记录逻辑总耗时。

## 7.12 测试或评测验证
> 从测试中找出成功、可重试失败、不可重试失败和脱敏各一例，解释断言证明什么。

```bash
pytest backend/tests/test_llm_service.py backend/tests/test_llm_observability.py -q
```

## 7.13 面试复述题
> 1. 为什么统一 LLM 边界比各节点直接 HTTP 更可靠？
>
> 2. reasoning 有值但 content 为空时应如何处理？
>
> 3. 网络重试与 SQL Repair 有什么不同？

## 7.14 掌握度检查与下一章
> 能画出一次逻辑调用内的多次 HTTP attempt；能给错误分类；能列出禁止记录的敏感信息。下一章组成最小闭环。
