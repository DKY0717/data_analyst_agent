# 第31章 实战三：从零重建最小 Agent

> 本章建议分两次、共 3～4 小时完成。你要在课程目录之外新建个人练习项目，只参考当前系统的接口职责，不复制生产实现。

## 31.1 学习目标

> 完成本章后，你应该能够：
>
> - 从空目录定义 Schema、LLM、Guard、Executor 与 Orchestrator 边界；
> - 用 Fake LLM 和临时 DuckDB 完成离线测试；
> - 保证模型 SQL 不会绕过安全校验直接执行；
> - 用结构化模型而不是字符串约定传递生成结果；
> - 明确 Mini Agent 不包含哪些生产能力；
> - 在不使用 LangGraph 的情况下解释状态机与失败路径。

## 31.2 前置知识

> 你应能写 Python 类/函数、Pydantic 模型、pytest 异步测试和简单 SQL；知道 OpenAI-compatible chat completions 的 content 不是可信输入；理解 SQLGlot AST 与 DuckDB 查询。

## 31.3 为什么需要这一模块

> 能读懂一个大型项目不等于能独立开发。现有代码已经替你做了大量决定，容易产生“我都理解”的错觉。从空目录重建会迫使你亲自决定接口、错误类型、依赖注入和测试顺序。
>
> 本练习故意不使用 LangGraph、Repair、Intent、权限、多轮、SSE 和前端。先证明最小闭环，再逐层增加能力，比一次复制 12 个节点更能检验基本功。

## 31.4 输入、输出与依赖

### 产品范围

> 输入是一条自然语言问题和一个只读 DuckDB；输出包含 validated SQL、columns、rows 和一段可选解释。模型只生成结构化查询计划，不持有数据库连接。

### 最小依赖

```text
Python 3.11+
pydantic
httpx（真实 LLM adapter 才需要）
sqlglot
duckdb 或 SQLAlchemy
pytest / pytest-asyncio
FastAPI（第二阶段可选）
```

### 明确不做

> 第一版不做 SQL Repair、权限、行过滤、LangGraph、会话、缓存、流式进度、图表和真实模型批量评测。面试时能清楚说出这些边界，比把半成品功能都塞进去更专业。

## 31.5 执行流程

```text
question
  → SchemaProvider.describe()
  → QueryPlanner.plan(question, schema)
  → QueryPlan(SQL + explanation)
  → SqlGuard.validate_and_limit(sql)
  → QueryExecutor.execute(validated_sql)
  → QueryResponse(columns + rows + sql + explanation)
```

> 所有错误都在对应边界转换为稳定类型。Orchestrator 负责顺序和组装，不负责解析 SQL、发 HTTP 或直接操作数据库。

## 31.6 当前代码地图

| 只参考职责 | 当前项目路径 | 不应复制的实现细节 |
|---|---|---|
| 配置 | `backend/app/config.py` | 全部历史兼容变量 |
| SchemaProvider | `backend/app/db/schema_loader.py` | 双数据库全部分支 |
| QueryPlanner adapter | `backend/app/services/llm_service.py` | 当前重试循环与 provider 兼容细节 |
| 结构化生成 | `backend/app/agents/sql_generator.py` | 完整 Prompt 文本 |
| SqlGuard | `backend/app/security/sql_guard.py` | 全部生产规则可后续扩展 |
| QueryExecutor | `backend/app/db/query_runner.py` | 子进程、PostgreSQL、审计全部能力 |
| Orchestrator | `backend/app/agents/graph.py` | LangGraph 12 节点实现 |

> 阅读这些文件时只写“输入、输出、错误、依赖”四列笔记，然后关掉源码再编码。不要边看边逐行翻写。

## 31.7 关键代码理解

### 推荐练习目录

```text
mini_nl2sql/
  pyproject.toml
  src/mini_agent/
    models.py
    schema.py
    planner.py
    guard.py
    executor.py
    service.py
    api.py          # 第二阶段可选
  tests/
    test_schema.py
    test_planner.py
    test_guard.py
    test_executor.py
    test_service.py
```

> 这个目录不要放进当前课程仓库，除非你明确决定把它作为新产品模块。个人练习应拥有独立 Git 历史，方便证明你能从零完成。

### 接口一：结构化模型

> `QueryPlan` 至少有非空 SQL 和简短说明；`QueryResult` 有 columns/rows；`QueryResponse` 组合 validated SQL、结果和解释。Pydantic 在边界拒绝空 SQL、错误字段和畸形 LLM JSON。

```python
class QueryPlan(BaseModel):
    sql: str
    explanation: str = ""

class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[object]]
```

> 这是接口骨架，不是完整答案。你还要决定最大字符串长度、行的可序列化类型和错误响应。

### 接口二：SchemaProvider

> 对外只暴露 `describe() -> SchemaSnapshot`。第一版可以从 DuckDB information_schema 读取表与列，只允许配置中的数据库路径。测试用临时数据库创建两张小表，断言 schema 不包含系统表和数据行。

### 接口三：QueryPlanner

> 定义 Protocol 或抽象接口：`async plan(question, schema) -> QueryPlan`。实现两个 adapter：FakePlanner 从测试字典返回固定计划；OpenAICompatiblePlanner 才负责 HTTP、content、JSON 和超时。
>
> service 测试只使用 FakePlanner。这样网络问题不会污染 Guard 与执行验证。

### 接口四：SqlGuard

> 第一版至少使用 SQLGlot 做：单语句、只允许 SELECT/WITH、拒绝 DDL/DML、拒绝危险文件/扩展函数、注入有限 LIMIT。不要用字符串包含判断代替 AST，也不要在 parse 失败时默认放行。

> Guard 输出 validated SQL 或抛稳定 `UnsafeSqlError`。Executor 的公开方法只接收 Guard 产生的受信类型会更安全；若不设计类型，也必须由 service 强制唯一调用顺序。

### 接口五：QueryExecutor

> 使用只读/隔离数据库，返回结构化 columns/rows，不把底层异常和连接字符串直接暴露给用户。第一版设置最大行数；超时可作为第二阶段增加。

### 接口六：AgentService

> Service 只编排五步，并通过构造参数注入 schema/planner/guard/executor。测试应能断言危险 SQL 到 Guard 后停止，Executor 未被调用；未知列在 Executor 失败后返回稳定错误，第一版不自动 Repair。

### 可选 API

> 核心离线测试全绿后再加一个 FastAPI `POST /query`。路由只校验请求/响应并调用 service，不在路由里写 Prompt、SQL 解析或数据库逻辑。

## 31.8 最小动手运行

> 在开始个人练习前，运行当前项目的 Guard 与 Executor 测试，观察公开契约，但不要复制实现。

```powershell
pytest backend/tests/test_sql_guard.py backend/tests/test_query_runner.py -q
```

> 在个人练习目录中，第一阶段只运行离线测试。

```powershell
pytest -q
```

> 真实 LLM adapter 应最后启用，并使用环境变量读取 Key；Key 不写入代码、fixture、日志或提交。

## 31.9 故障注入实验

> FakePlanner 依次提供以下输出，并断言失败停在正确边界：

| 输入 | 预期边界 | Executor 是否调用 |
|---|---|---|
| 非 JSON/缺 SQL 字段 | Planner adapter/Pydantic | 否 |
| `DROP TABLE ...` | SqlGuard | 否 |
| 两条 SELECT | SqlGuard | 否 |
| `SELECT missing FROM orders` | Executor/Schema 校验 | 是，随后稳定失败 |
| 合法 SELECT 无 LIMIT | Guard 注入 LIMIT 后执行 | 是 |
| 合法聚合 | 完整成功 | 是 |

> 再让 Executor 抛一个带数据库路径的原始异常，确认 API/Service 对外只返回稳定类型，不泄露本机路径。

## 31.10 调试路径与常见误判

> Planner 失败只查 HTTP/content/JSON/Pydantic；Guard 失败查 AST 和策略；Executor 失败查 Schema/连接/SQL；Service 顺序失败查依赖注入和短路。不要在一个 try/except 中把所有错误改成“Agent failed”。
>
> 常见误判一：不用 LangGraph 就不算 Agent。最小 Agent 的核心是受控感知、决策、工具调用与反馈闭环，框架不是定义本身。
>
> 常见误判二：先接真实模型更真实。它会同时引入网络、响应格式和采样变量，阻碍核心设计。
>
> 常见误判三：模型承诺只生成 SELECT 就足够。安全必须由程序级 Guard enforce。
>
> 常见误判四：为了简单把 Schema、Prompt、HTTP、Guard 和执行写在一个函数。这样无法替换依赖，也无法证明危险 SQL没有执行。
>
> 常见误判五：Mini Agent 跑通就等于生产项目。它没有权限、Repair、审计、分片评测和前端等生产能力。

## 31.11 独立编码练习

> 按两个阶段完成，不要跳步。

### 阶段 A：离线核心

```text
[ ] 定义三类模型和稳定错误
[ ] 临时 DuckDB SchemaProvider
[ ] FakePlanner
[ ] SQLGlot Guard
[ ] Executor 最大行数
[ ] Service 强制顺序与短路
[ ] 每个接口至少成功/失败各一例
[ ] 全程零网络
```

### 阶段 B：真实适配

```text
[ ] OpenAI-compatible adapter
[ ] content 为空稳定失败
[ ] 总重试预算与 timeout
[ ] 可选 FastAPI 路由
[ ] 3 个非敏感 smoke 问题
[ ] 保存 provider/model/HEAD，不保存 Key
```

> 完成后让自己在白板上重新写一遍接口签名。如果只能展示代码、无法口述设计，说明还没有真正掌握。

## 31.12 测试或评测验证

> 最低验收目标：
>
> - 单元测试覆盖模型、Schema、Guard 和错误；
> - service 测试证明调用顺序和危险 SQL 短路；
> - 临时数据库每次独立，不依赖测试顺序；
> - FakePlanner 测试不需要 API Key；
> - 真实 smoke 明确与离线回归分开。

```text
离线证据：测试数量、通过结果、无网络
真实证据：provider、model、日期、问题数、逐例状态
边界：未实现权限/Repair/多轮/评测门禁
```

> 不要用个人 Mini Agent 的 3 条 smoke 结果替代当前项目的完整 case pack，也不要把当前项目的历史结果算作你个人重建实现的成绩。

## 31.13 面试复述题

> **问题：不用 LangGraph，怎么实现一个最小但安全的 NL2SQL Agent？**
>
> 合格回答：定义可替换的 SchemaProvider、QueryPlanner、SqlGuard、QueryExecutor 与 Service；Planner 输出 Pydantic QueryPlan；SQL 必须经过 SQLGlot 单语句只读校验和 LIMIT 后才能执行；FakePlanner + 临时 DB 完成离线测试，最后才接真实模型。
>
> **追问：何时再引入 LangGraph？**
>
> 应回答：当流程出现澄清暂停、多轮状态、Repair 循环、权限重新校验、进度事件和审计汇总等显式状态/条件边时，引入图编排能提升可读性与测试性；简单线性五步无需为框架而框架。

## 31.14 掌握度检查与下一章

> 如果你能关掉当前仓库，从空目录写出离线核心，并用测试证明危险 SQL不会进入 Executor，就达成课程“可独立重建核心 Agent”的目标。
>
> 下一章把全部能力组织成面试表达：30 秒定位、5 分钟架构、10 分钟演示、事故复盘，以及如何诚实说明 AI 辅助开发与个人贡献。
