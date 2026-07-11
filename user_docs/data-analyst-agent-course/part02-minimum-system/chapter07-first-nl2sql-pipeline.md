# 第七章 完成第一条自然语言转 SQL 链路

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 7.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 画出最小 NL2SQL 闭环的输入、输出和依赖；
> 2. 说明 SQL Generator 如何组合物理 Schema、业务语义和用户问题；
> 3. 解释 QueryRunner 如何返回列、行、耗时和错误类型；
> 4. 理解 Answer Generator 为什么放在查询成功之后；
> 5. 使用 API 或测试观察一次查询的结果结构；
> 6. 说出“最小链路”与“完整安全链路”的差异。

## 7.2 问题场景

> 用户不会主动告诉系统 `orders.total_amount` 或 `strftime(order_date, '%Y-%m')`。用户只会说“统计 2024 年每个月的销售额”。最小系统需要把自然语言转换成可执行 SQL，再把数据库结果转换回用户能理解的答案。
>
> 本章只关注数据流是否贯通，暂时不展开 Intent Guard、SQL Guard、权限和自动修复。这样做不是因为这些能力不重要，而是为了先看清一条成功路径由哪些组件组成，下一部分再逐层加入保护。

## 7.3 最小闭环

```text
用户问题
  ↓
SchemaLoader 读取真实结构
  ↓
SQLGenerator 组合 Schema + 语义摘要 + 问题
  ↓
OpenAI-compatible LLM 返回结构化 SQL
  ↓
QueryRunner 执行 SQL
  ↓
AnswerGenerator 根据结果生成解释
  ↓
QueryResponse 返回前端
```

> 这条路径的关键是每个步骤都有明确输入和输出。SQL Generator 不直接打开数据库，QueryRunner 不负责理解中文，Answer Generator 不负责重新计算指标。职责越清楚，后续替换实现越容易。

## 7.4 SQLGenerator 如何准备上下文

### 7.4.1 物理 Schema 与业务语义同时提供

```python
def _format_schema(self, schema_context):
    physical_schema = format_physical_schema(schema_context)
    semantic_summary = semantic_loader.format_for_prompt()
    return "\n".join([
        "物理数据库 Schema:",
        physical_schema,
        "",
        "业务语义层:",
        semantic_summary,
    ])
```

> 物理 Schema 回答“有哪些真实表和字段”，语义层回答“销售额、退款率等业务词应该如何计算”。只提供物理字段会让模型自行猜口径，只提供语义又会让模型找不到可执行字段；两部分需要同时出现。

### 7.4.2 结构化意图和多轮上下文

> 当前 `SQLGenerator.generate()` 接收 `conversation_context` 和 `analysis_intent` 两个可选参数。第一版最小链路可以为空，但完整系统会把最近一轮摘要、指标、维度、过滤和 Grounding 结果放进 Prompt，减少模型自行推断。

```python
result = await self.client.generate_sql(
    question,
    schema_str,
    conversation_context,
    intent_str,
)
```

> 这说明 SQL Generator 的职责不是“只发一个问题给模型”，而是把已经由确定性或半确定性模块整理过的上下文传递给模型。下一部分会详细解释这些上游模块如何产生结构化意图。

## 7.5 结构化 SQL 输出

```python
output = SQLGeneratorOutput(
    sql=result["sql"],
    tables=result.get("tables", []),
    columns=columns,
    explanation=result.get("explanation", ""),
)
```

> `SQLGeneratorOutput` 用 Pydantic 模型固定了输出边界。`tables` 和 `explanation` 来自模型，`columns` 则由 SQLGlot 从 SQL AST 中提取，避免完全相信模型自己报告的字段列表。

> 这里的 AST 解析只是为了产生元数据，不等于安全校验。SQL 解析失败时 `_extract_columns()` 返回空列表，但生成流程仍会把 SQL 交给上游异常处理；安全执行要等第八章的 SQL Guard。

## 7.6 QueryRunner 执行查询

### 7.6.1 两种执行模式

| 模式 | 位置 | 适合场景 | 主要边界 |
|---|---|---|---|
| direct | 当前进程 | 本地调试和简单测试 | 与应用进程共享资源 |
| sandbox | 子进程 | 受保护运行 | 需要传递连接配置和超时 |

> `QueryRunner.execute()` 根据 `SANDBOX_MODE` 选择模式。当前配置默认倾向沙箱；本地调试可以显式关闭，但关闭后不能把这条路径误当成生产隔离。

### 7.6.2 稳定的执行结果

```python
{
    "success": True,
    "columns": ["month", "sales_amount"],
    "rows": [["2024-01", 12345.67]],
    "execution_time_ms": 18,
    "row_count": 1,
    "execution_mode": "direct"
}
```

> 成功结果包含列名、数据行、耗时、行数和执行模式。失败结果包含稳定的 `error` 和 `error_type`，详细的数据库诊断只供内部修复链路使用。这样前端可以展示耗时，评测可以判断是否成功，SQL Repair 可以根据错误类型工作。

### 7.6.3 PostgreSQL 的语句超时

> 在 PostgreSQL 直连路径中，执行器会在当前事务内设置 `statement_timeout`，避免一个查询无限占用数据库。DuckDB 和沙箱路径也有自己的超时控制；这些限制属于执行层，不能由 LLM Prompt 代替。

## 7.7 AnswerGenerator 的职责

```python
answer = await self.client.generate_answer(question, sql, query_result)
```

> Answer Generator 位于查询成功之后，输入包括原问题、最终 SQL 和查询结果。它负责把表格结果解释成自然语言，不负责重新访问数据库或更改 SQL。

> 如果查询失败，流程不应该让 Answer Generator 把错误结果包装成“看起来合理”的答案。完整 Agent 会先进入 SQL Repair，重试耗尽后再返回稳定失败提示。

## 7.8 API 响应如何组装

```python
response = QueryResponse(
    question=result["question"],
    status=result.get("status", "completed"),
    sql=result.get("validated_sql") or result.get("generated_sql") or "",
    columns=query_result.get("columns", []),
    rows=query_result.get("rows", []),
    answer=result.get("answer") or "抱歉，处理您的问题时遇到困难，请尝试换个问法。",
)
```

> API 层把 Agent state 和数据库结果转换成前端契约。即使被阻断或重试耗尽，也尽量返回稳定的字段形状，方便前端展示状态和审计信息。后续加入权限、澄清和 SSE 时，仍然沿用这个响应边界。

## 7.9 最小链路的风险

> 在完整 Guard 接入前，最小链路存在以下风险：

| 风险 | 为什么会发生 | 完整系统由谁处理 |
|---|---|---|
| 模型生成 `DELETE` 等写操作 | 模型输出不受信任 | Intent Guard、SQL Guard |
| 查询读取敏感字段 | SQL 可能引用未授权列 | Data Permission Guard |
| SQL 执行失败 | 字段、方言或 JOIN 猜错 | SQL Repair Agent |
| 业务口径错误 | 只提供物理字段，缺少语义 | Intent、Semantic、Grounding |
| 查询耗时过长 | 没有执行层保护 | QueryRunner、Sandbox、超时 |

> 因此“跑通一次成功查询”只证明组件可以连接，不证明系统安全或结果正确。学习过程中应该把成功路径和保护路径分开验证。

## 7.10 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/agents/sql_generator.py` | Schema 和问题到 SQL | Prompt 上下文、结构化输出、AST 字段提取 |
| `backend/app/db/query_runner.py` | 执行 SQL | direct/sandbox、结果和错误 |
| `backend/app/agents/answer_generator.py` | 结果到自然语言 | 调用时机和错误边界 |
| `backend/app/api/query.py` | HTTP 查询入口 | 请求、Agent 调用、响应组装 |
| `backend/app/models/schemas.py` | 响应契约 | `QueryResponse` 的稳定字段 |
| `backend/tests/test_sql_generator.py` | SQL 生成行为测试 | Fake Client 和输出模型 |
| `backend/tests/test_query_runner.py` | 执行器测试 | 成功、错误和执行模式 |

## 7.11 动手验证

> 首先运行不需要真实模型的单元测试：

```bash
pytest backend/tests/test_sql_generator.py backend/tests/test_query_runner.py -q
```

> 然后在配置了可用 OpenAI-compatible 端点的环境中，启动后端并发送一个只读问题：

```bash
curl -X POST http://127.0.0.1:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question":"统计 2024 年每个月的销售额"}'
```

> 成功时，响应 `data` 中至少应包含 `question`、`sql`、`columns`、`rows`、`answer` 和 `status`。如果外部模型不可达，响应失败不代表本章代码一定错误，应结合 `test_sql_generator.py` 的确定性结果区分网络问题和业务问题。

## 7.12 常见错误

### 生成结果没有 `sql`

> 这是结构化输出契约错误。先查看模型响应解析和 Fake Client 返回值，不要在 API 层用 `result.get("sql", "")` 默默吞掉错误，否则后续执行器会收到空 SQL。

### 查询字段不存在

> 可能是模型使用了错误表名、字段名或 SQL 方言。先打印经过脱敏的 SQL 结构，核对 `/api/schema` 返回的实际字段；完整系统还会通过 SQL Repair 反馈执行错误。

### 查询结果为空

> 空结果不一定是执行失败。检查时间范围、状态筛选、JOIN 条件和测试数据库是否已 seed；同时区分 `success=True, rows=[]` 和 `success=False`。

### 真实模型失败但单测通过

> 单测通常使用 Mock 或 Fake Client，只验证业务编排和解析。真实模型还受到网络、Key、配额、模型能力和 Prompt 变化影响，二者是不同的证据层级。

## 7.13 本章小结

> 最小 NL2SQL 链路把“问题、Schema、模型、执行器和答案”串成了一个闭环：SQL Generator 负责生成，QueryRunner 负责执行，Answer Generator 负责解释，API 层负责稳定返回。但模型输出仍然不可信，最小链路的成功不能替代安全、权限、修复和评测。下一章会先从最重要的安全边界开始补齐。

## 7.14 练习

1. 画出 `POST /api/chat/query` 到 `QueryResponse` 的调用链，并标出每个模块的输入输出。
2. 用一个合法但返回零行的 SQL 验证“成功但空结果”和“执行失败”的区别。
3. 在 Fake Client 中返回缺少 `explanation` 的 JSON，观察 Pydantic 默认值如何工作。
4. 解释为什么 Answer Generator 不能在 QueryRunner 失败后直接生成结论。
5. 列出至少三种必须在下一章加入的安全控制。

## 7.15 下一章衔接

> 最小链路已经证明系统能完成一次分析，但它还没有建立信任边界。下一章会实现 Intent Guard、SQLGlot AST 校验、LIMIT 约束、沙箱和错误分类，让“能生成 SQL”变成“只执行经过控制的 SQL”。
