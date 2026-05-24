# Data Analyst Agent 开发文档 v0.1

## 1. 项目名称

**Data Analyst Agent：自然语言驱动的数据库分析与 SQL 优化系统**

---

## 2. 项目定位

本项目旨在构建一个面向业务数据分析场景的智能 Agent 系统。用户可以通过自然语言提出数据分析问题，系统自动完成数据库 Schema 理解、SQL 生成、SQL 安全校验、SQL 执行、错误反馈修复、结果解释、图表生成以及 SQL 优化建议。

本项目不是简单的 Text-to-SQL Demo，而是一个围绕自然语言数据分析任务构建的可控、可校验、可修复、可优化的数据分析系统。

### 2.1 一句话描述

构建一个基于多 Agent 工作流的智能数据分析系统，实现从自然语言问题到安全 SQL 查询、执行反馈修复、结果解释和 SQL 优化建议的完整闭环。

### 2.2 项目核心价值

本项目主要解决以下问题：

1. 用户不会 SQL，但需要从数据库中完成业务分析。
2. 大模型直接生成 SQL 存在表字段幻觉、语法错误和危险 SQL 风险。
3. SQL 查询不仅要能执行，还需要安全、正确、可优化。
4. 传统 Text-to-SQL 系统缺少执行反馈、自动修复和执行计划分析能力。

---

## 3. 项目目标

### 3.1 MVP 目标

第一阶段实现最小可用版本：

1. 用户输入自然语言问题。
2. 系统读取数据库 Schema。
3. 系统生成 SQL。
4. 系统进行 SQL 安全校验。
5. 系统执行 SQL。
6. 若 SQL 报错，系统自动修复。
7. 系统返回查询结果和自然语言解释。

### 3.2 增强目标

第二阶段在 MVP 基础上增加：

1. Schema Retriever：基于 ChromaDB 的表字段语义检索。
2. SQL Optimizer：基于规则和执行计划的 SQL 优化建议。
3. EXPLAIN ANALYZE：分析 SQL 查询计划。
4. 自动图表生成：根据查询结果生成 ECharts 图表。
5. 查询历史管理：保存用户问题、SQL、结果和执行状态。
6. 评估体系：统计 SQL 执行成功率、修复成功率、平均修复次数和优化前后查询耗时。

### 3.3 非目标

第一版不做以下内容：

1. 不训练或微调大模型。
2. 不做复杂权限系统。
3. 不做多租户系统。
4. 不做完整 BI 平台。
5. 不做 Kubernetes 部署。
6. 不做复杂分布式数据库优化。

---

## 4. 技术栈

### 4.1 后端

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- LangGraph
- SQLGlot
- DuckDB
- PostgreSQL

### 4.2 前端

- Vue 3
- Element Plus
- Axios
- ECharts

### 4.3 Agent 与 LLM

- LangGraph：Agent 工作流编排
- LLM API：SQL 生成、SQL 修复、结果解释
- Prompt Engineering：结构化输出约束
- Tool Calling：数据库查询、SQL 校验、执行计划分析

### 4.4 向量检索，可选增强模块

- ChromaDB
- Embedding Model

### 4.5 工程化

- Git
- Docker
- Docker Compose
- pytest
- dotenv
- logging

---

## 5. 总体架构

### 5.1 系统架构图

```text
User
  ↓
Vue Frontend
  ↓
FastAPI Backend
  ↓
LangGraph Agent Orchestrator
  ├── Intent Planner
  ├── Schema Loader / Schema Retriever
  ├── SQL Generator
  ├── SQL Guard
  ├── SQL Executor
  ├── SQL Repair Agent
  ├── SQL Optimizer
  └── Answer Generator
  ↓
Database Layer
  ├── DuckDB
  └── PostgreSQL
```

### 5.2 核心流程

```text
自然语言问题
  ↓
读取或检索相关 Schema
  ↓
生成 SQL
  ↓
SQL 安全校验
  ↓
执行 SQL
  ↓
如果失败：SQL Repair
  ↓
如果成功：生成结果解释
  ↓
可选：执行计划分析与 SQL 优化建议
  ↓
返回 SQL、结果表格、图表、解释和优化建议
```

---

## 6. 项目目录结构

```text
data-analyst-agent/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   │
│   │   ├── api/
│   │   │   ├── query.py
│   │   │   ├── schema.py
│   │   │   └── history.py
│   │   │
│   │   ├── agents/
│   │   │   ├── graph.py
│   │   │   ├── state.py
│   │   │   ├── intent_planner.py
│   │   │   ├── sql_generator.py
│   │   │   ├── sql_repair.py
│   │   │   ├── sql_optimizer.py
│   │   │   └── answer_generator.py
│   │   │
│   │   ├── db/
│   │   │   ├── connection.py
│   │   │   ├── schema_loader.py
│   │   │   ├── query_runner.py
│   │   │   └── explain_runner.py
│   │   │
│   │   ├── retriever/
│   │   │   ├── schema_indexer.py
│   │   │   └── schema_retriever.py
│   │   │
│   │   ├── security/
│   │   │   └── sql_guard.py
│   │   │
│   │   ├── services/
│   │   │   ├── llm_service.py
│   │   │   ├── chart_service.py
│   │   │   └── history_service.py
│   │   │
│   │   ├── models/
│   │   │   └── schemas.py
│   │   │
│   │   └── utils/
│   │       ├── logger.py
│   │       └── exceptions.py
│   │
│   ├── tests/
│   │   ├── test_sql_guard.py
│   │   ├── test_schema_loader.py
│   │   ├── test_query_runner.py
│   │   └── test_agent_graph.py
│   │
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── agent.js
│   │   ├── components/
│   │   │   ├── QueryInput.vue
│   │   │   ├── SQLPanel.vue
│   │   │   ├── ResultTable.vue
│   │   │   ├── ChartPanel.vue
│   │   │   ├── ExplainPanel.vue
│   │   │   └── OptimizationPanel.vue
│   │   ├── views/
│   │   │   └── Home.vue
│   │   └── main.js
│   │
│   ├── package.json
│   └── Dockerfile
│
├── database/
│   ├── init.sql
│   ├── seed_data.py
│   └── sample_data/
│
├── docs/
│   ├── project_requirement.md
│   ├── database_design.md
│   ├── api_design.md
│   ├── agent_workflow.md
│   ├── sql_guard_rules.md
│   └── evaluation_plan.md
│
├── evaluation/
│   ├── test_questions.json
│   ├── evaluate.py
│   └── report.md
│
├── docker-compose.yml
├── README.md
└── .env.example
```

---

## 7. 数据库设计

第一版使用电商业务数据集，便于展示销售分析、用户分析、商品分析、地区分析和退款分析。

### 7.1 表设计概览

| 表名 | 含义 |
|---|---|
| customers | 用户信息表 |
| regions | 地区信息表 |
| products | 商品信息表 |
| categories | 商品类别表 |
| orders | 订单表 |
| order_items | 订单明细表 |
| payments | 支付表 |
| refunds | 退款表 |
| campaigns | 营销活动表，可选 |

### 7.2 customers

| 字段 | 类型 | 含义 |
|---|---|---|
| customer_id | INTEGER | 用户 ID |
| customer_name | VARCHAR | 用户姓名 |
| gender | VARCHAR | 性别 |
| age | INTEGER | 年龄 |
| region_id | INTEGER | 地区 ID |
| register_date | DATE | 注册日期 |

### 7.3 regions

| 字段 | 类型 | 含义 |
|---|---|---|
| region_id | INTEGER | 地区 ID |
| region_name | VARCHAR | 地区名称 |
| province | VARCHAR | 省份 |
| city | VARCHAR | 城市 |

### 7.4 categories

| 字段 | 类型 | 含义 |
|---|---|---|
| category_id | INTEGER | 类别 ID |
| category_name | VARCHAR | 类别名称 |

### 7.5 products

| 字段 | 类型 | 含义 |
|---|---|---|
| product_id | INTEGER | 商品 ID |
| product_name | VARCHAR | 商品名称 |
| category_id | INTEGER | 类别 ID |
| price | DECIMAL | 商品价格 |
| cost | DECIMAL | 商品成本 |
| created_at | DATE | 上架日期 |

### 7.6 orders

| 字段 | 类型 | 含义 |
|---|---|---|
| order_id | INTEGER | 订单 ID |
| customer_id | INTEGER | 用户 ID |
| order_date | DATE | 下单日期 |
| status | VARCHAR | 订单状态 |
| total_amount | DECIMAL | 订单总金额 |

### 7.7 order_items

| 字段 | 类型 | 含义 |
|---|---|---|
| item_id | INTEGER | 明细 ID |
| order_id | INTEGER | 订单 ID |
| product_id | INTEGER | 商品 ID |
| quantity | INTEGER | 购买数量 |
| unit_price | DECIMAL | 商品单价 |

### 7.8 payments

| 字段 | 类型 | 含义 |
|---|---|---|
| payment_id | INTEGER | 支付 ID |
| order_id | INTEGER | 订单 ID |
| payment_method | VARCHAR | 支付方式 |
| payment_status | VARCHAR | 支付状态 |
| paid_amount | DECIMAL | 支付金额 |
| paid_at | TIMESTAMP | 支付时间 |

### 7.9 refunds

| 字段 | 类型 | 含义 |
|---|---|---|
| refund_id | INTEGER | 退款 ID |
| order_id | INTEGER | 订单 ID |
| refund_amount | DECIMAL | 退款金额 |
| refund_reason | VARCHAR | 退款原因 |
| refund_date | DATE | 退款日期 |

---

## 8. Agent 工作流设计

### 8.1 Agent 状态定义

Agent 在 LangGraph 中共享一个状态对象，建议定义为：

```python
class AgentState(TypedDict):
    question: str
    schema_context: dict
    generated_sql: str
    validated_sql: str
    is_sql_safe: bool
    validation_error: str | None
    execution_success: bool
    query_result: dict | None
    execution_error: str | None
    retry_count: int
    answer: str | None
    optimization_suggestions: list[str]
```

### 8.2 节点一：Schema Loader / Schema Retriever

功能：

1. 读取数据库所有表结构。
2. 返回表名、字段名、字段类型、主外键关系。
3. 第二阶段可加入 ChromaDB，只检索相关表和字段。

输入：

```text
用户自然语言问题
```

输出：

```json
{
  "tables": ["orders", "customers"],
  "columns": {
    "orders": ["order_id", "customer_id", "order_date", "total_amount"],
    "customers": ["customer_id", "region_id"]
  }
}
```

### 8.3 节点二：SQL Generator

功能：

1. 根据用户问题和 Schema 生成 SQL。
2. SQL 方言第一版使用 DuckDB，第二版支持 PostgreSQL。
3. 输出结构化 JSON，避免自由文本。

输出示例：

```json
{
  "sql": "SELECT DATE_TRUNC('month', order_date) AS month, SUM(total_amount) AS sales FROM orders GROUP BY 1 ORDER BY 1",
  "tables": ["orders"],
  "columns": ["order_date", "total_amount"],
  "explanation": "该 SQL 按月份统计订单销售额。"
}
```

### 8.4 节点三：SQL Guard

功能：

1. 使用 SQLGlot 解析 SQL。
2. 只允许 SELECT 和 WITH 查询。
3. 禁止 DROP、DELETE、UPDATE、INSERT、ALTER、TRUNCATE、CREATE。
4. 禁止多语句执行。
5. 自动添加 LIMIT。
6. 检查是否包含危险函数或系统表访问。

输出：

```json
{
  "is_safe": true,
  "sanitized_sql": "SELECT ... LIMIT 1000",
  "reason": null
}
```

### 8.5 节点四：SQL Executor

功能：

1. 执行 SQL。
2. 返回字段名、数据行、执行耗时。
3. 捕获数据库错误。
4. 设置查询超时。

输出成功示例：

```json
{
  "success": true,
  "columns": ["month", "sales"],
  "rows": [["2024-01", 12000.5]],
  "execution_time_ms": 42
}
```

输出失败示例：

```json
{
  "success": false,
  "error": "column customer_name does not exist"
}
```

### 8.6 节点五：SQL Repair

触发条件：

```text
SQL 执行失败 && retry_count < 3
```

输入：

1. 用户原始问题。
2. 原 SQL。
3. 数据库错误信息。
4. Schema 上下文。

输出：

```json
{
  "repaired_sql": "...",
  "repair_reason": "原 SQL 使用了不存在的字段 customer_name，已改为 customers.customer_name。"
}
```

### 8.7 节点六：Answer Generator

功能：

1. 根据查询结果生成自然语言解释。
2. 不夸大结果。
3. 不编造数据库中不存在的信息。
4. 说明 SQL 查询逻辑。

输出示例：

```text
查询结果显示，2024 年 1 月销售额为 12000.5 元，2 月销售额为 14500.8 元。从整体趋势看，销售额呈现上升趋势。
```

### 8.8 节点七：SQL Optimizer，第二阶段

功能：

1. 对 SQL 执行 EXPLAIN ANALYZE。
2. 识别全表扫描、低效 JOIN、排序成本过高等问题。
3. 输出优化建议。
4. 可选：生成重写后的 SQL。

输出示例：

```json
{
  "issues": [
    "orders 表发生全表扫描",
    "order_date 字段用于时间过滤，建议建立索引"
  ],
  "suggestions": [
    "建议在 orders(order_date) 上建立索引",
    "避免 SELECT *，只保留必要字段"
  ]
}
```

---

## 9. SQL 安全设计

### 9.1 基本原则

1. 永远不直接执行 LLM 生成的原始 SQL。
2. SQL 必须经过 SQL Guard 校验。
3. 数据库账号使用只读权限。
4. 查询必须设置超时。
5. 查询结果必须限制返回行数。

### 9.2 允许语句

```sql
SELECT
WITH
EXPLAIN
```

### 9.3 禁止语句

```sql
DROP
DELETE
UPDATE
INSERT
ALTER
TRUNCATE
CREATE
MERGE
CALL
EXECUTE
GRANT
REVOKE
```

### 9.4 其他限制

1. 禁止多语句执行。
2. 禁止访问系统表。
3. 禁止写文件。
4. 禁止执行外部函数。
5. 没有 LIMIT 的 SELECT 自动添加 LIMIT 1000。

---

## 10. ChromaDB 设计，可选增强模块

第一版不必须加入 ChromaDB。第二版可用于构建 Schema Retriever。

### 10.1 ChromaDB 存储内容

ChromaDB 不存业务数据，只存帮助 LLM 理解数据库的上下文。

可存储内容包括：

1. 表说明。
2. 字段说明。
3. 主外键关系。
4. 指标定义。
5. 历史 SQL 样例。
6. 常见业务问题模板。

### 10.2 存储示例

```json
{
  "id": "table_orders",
  "document": "orders 表存储订单信息，包括 order_id、customer_id、order_date、total_amount、status 字段，可用于分析销售额、订单量、客户购买行为。",
  "metadata": {
    "type": "table",
    "table_name": "orders"
  }
}
```

### 10.3 检索流程

```text
用户问题
  ↓
Embedding
  ↓
ChromaDB 检索相关表、字段、指标定义
  ↓
构造 Schema Context
  ↓
传入 SQL Generator
```

---

## 11. API 设计

### 11.1 POST /api/chat/query

功能：接收自然语言问题，返回 SQL、结果、解释和优化建议。

请求：

```json
{
  "question": "统计 2024 年每个月的销售额"
}
```

响应：

```json
{
  "question": "统计 2024 年每个月的销售额",
  "sql": "SELECT ...",
  "is_sql_safe": true,
  "columns": ["month", "sales"],
  "rows": [],
  "answer": "2024 年每个月销售额如下...",
  "execution_time_ms": 42,
  "retry_count": 0,
  "optimization_suggestions": []
}
```

### 11.2 GET /api/schema

功能：返回数据库 Schema。

响应：

```json
{
  "tables": {
    "orders": [
      {"column": "order_id", "type": "INTEGER"},
      {"column": "order_date", "type": "DATE"}
    ]
  }
}
```

### 11.3 POST /api/sql/validate

功能：校验 SQL 是否安全。

请求：

```json
{
  "sql": "SELECT * FROM orders"
}
```

响应：

```json
{
  "is_safe": true,
  "sanitized_sql": "SELECT * FROM orders LIMIT 1000",
  "reason": null
}
```

### 11.4 POST /api/sql/execute

功能：执行已校验 SQL。

请求：

```json
{
  "sql": "SELECT * FROM orders LIMIT 10"
}
```

响应：

```json
{
  "success": true,
  "columns": [],
  "rows": [],
  "execution_time_ms": 30
}
```

### 11.5 POST /api/sql/explain

功能：返回 SQL 执行计划和优化建议。

请求：

```json
{
  "sql": "SELECT * FROM orders WHERE order_date >= '2024-01-01'"
}
```

响应：

```json
{
  "plan": "...",
  "issues": [],
  "suggestions": []
}
```

---

## 12. 前端页面设计

### 12.1 页面模块

前端首页包含以下区域：

1. 自然语言输入框。
2. 生成 SQL 展示区。
3. SQL 安全状态展示区。
4. 查询结果表格。
5. 图表展示区。
6. 自然语言解释区。
7. SQL 优化建议区。
8. 查询历史区，可选。

### 12.2 组件划分

```text
Home.vue
  ├── QueryInput.vue
  ├── SQLPanel.vue
  ├── ResultTable.vue
  ├── ChartPanel.vue
  ├── AnswerPanel.vue
  ├── ExplainPanel.vue
  └── OptimizationPanel.vue
```

### 12.3 用户交互流程

```text
用户输入问题
  ↓
点击“开始分析”
  ↓
前端调用 POST /api/chat/query
  ↓
展示生成 SQL
  ↓
展示查询结果
  ↓
展示图表和解释
  ↓
展示优化建议
```

---

## 13. Prompt 设计

### 13.1 SQL Generator Prompt

目标：让 LLM 根据用户问题和 Schema 生成 SQL。

约束：

1. 只输出 JSON。
2. 只生成 SELECT 或 WITH。
3. 不生成危险 SQL。
4. SQL 方言使用 DuckDB 或 PostgreSQL。
5. 字段必须来自提供的 Schema。

输出格式：

```json
{
  "sql": "...",
  "tables": ["..."],
  "columns": ["..."],
  "explanation": "..."
}
```

### 13.2 SQL Repair Prompt

输入：

1. 用户问题。
2. 原 SQL。
3. 数据库错误。
4. Schema。

输出格式：

```json
{
  "repaired_sql": "...",
  "repair_reason": "..."
}
```

### 13.3 Answer Generator Prompt

要求：

1. 只根据查询结果解释。
2. 不编造没有查询出来的信息。
3. 对空结果进行合理说明。
4. 对数值结果给出简洁总结。

---

## 14. SQL 优化规则

### 14.1 静态规则

| 问题 | 优化建议 |
|---|---|
| SELECT * | 只查询必要字段 |
| WHERE 中对索引列使用函数 | 改写为范围查询 |
| 大表 JOIN 前无过滤 | 先过滤再 JOIN |
| 无 LIMIT | 添加 LIMIT |
| 重复子查询 | 改为 CTE |
| ORDER BY 大结果集 | 添加 LIMIT 或索引 |
| JOIN 缺少 ON 条件 | 阻止执行或提示风险 |

### 14.2 执行计划规则

| 执行计划现象 | 可能问题 | 建议 |
|---|---|---|
| Seq Scan | 未使用索引 | 建立索引或优化 WHERE 条件 |
| Nested Loop | 大表连接低效 | 检查 JOIN 条件或索引 |
| Sort 耗时高 | 排序数据量大 | 添加 LIMIT 或索引 |
| Hash Join 数据量大 | JOIN 前过滤不足 | 先过滤再连接 |
| Actual Rows 远大于 Estimated Rows | 统计信息不准确 | 更新统计信息 |

---

## 15. 测试设计

### 15.1 单元测试

需要测试以下模块：

1. SQL Guard。
2. Schema Loader。
3. Query Runner。
4. SQL Repair。
5. Agent Graph。

### 15.2 SQL Guard 测试用例

| 输入 SQL | 预期结果 |
|---|---|
| SELECT * FROM orders | 通过 |
| DROP TABLE orders | 拦截 |
| DELETE FROM orders | 拦截 |
| UPDATE orders SET status='x' | 拦截 |
| SELECT * FROM orders; DROP TABLE orders | 拦截 |
| WITH t AS (...) SELECT * FROM t | 通过 |

### 15.3 评估测试集

构建 `evaluation/test_questions.json`，至少包含 30 到 50 个问题。

问题类型：

1. 简单查询。
2. 条件过滤。
3. 聚合统计。
4. 多表 JOIN。
5. 时间序列分析。
6. 排名分析。
7. 退款率分析。
8. 复购率分析。
9. 同比环比分析。
10. 异常查询问题。

### 15.4 评估指标

| 指标 | 含义 |
|---|---|
| SQL 执行成功率 | 成功执行 SQL 的比例 |
| SQL 修复成功率 | 初次失败后修复成功的比例 |
| 平均修复次数 | 每个问题平均进入修复流程的次数 |
| 危险 SQL 拦截率 | 成功拦截危险 SQL 的比例 |
| 平均查询耗时 | SQL 执行平均耗时 |
| 优化前后耗时变化 | SQL 优化带来的性能提升 |
| Schema 选择准确率 | 相关表字段检索是否正确 |

---

## 16. 开发阶段规划

### 阶段一：基础工程搭建

目标：项目可以启动，前后端可以通信。

任务：

1. 创建项目目录。
2. 搭建 FastAPI 后端。
3. 搭建 Vue 前端。
4. 配置数据库连接。
5. 实现 mock 查询接口。

验收标准：

1. 后端可以通过 `uvicorn` 启动。
2. FastAPI `/docs` 可访问。
3. 前端可以调用后端接口。

### 阶段二：数据库与 Schema Loader

目标：数据库可以创建、填充和读取 Schema。

任务：

1. 编写 `init.sql`。
2. 编写 `seed_data.py`。
3. 实现 `schema_loader.py`。
4. 实现 `GET /api/schema`。

验收标准：

1. 数据库建表成功。
2. 模拟数据插入成功。
3. 后端能返回完整 Schema。

### 阶段三：SQL Guard 与 SQL Executor

目标：SQL 可以被安全校验和执行。

任务：

1. 实现 SQLGlot AST 解析。
2. 实现危险 SQL 拦截。
3. 实现自动 LIMIT 注入。
4. 实现 Query Runner。
5. 编写 SQL Guard 单元测试。

验收标准：

1. SELECT 可执行。
2. DROP、DELETE、UPDATE 被拦截。
3. 查询结果正常返回。

### 阶段四：SQL Generator

目标：接入 LLM，生成可执行 SQL。

任务：

1. 编写 SQL Generator Prompt。
2. 实现 LLM 调用服务。
3. 实现结构化 JSON 输出解析。
4. 与 SQL Guard 和 SQL Executor 串联。

验收标准：

1. 用户输入自然语言问题后，系统能生成 SQL。
2. 生成 SQL 经过安全校验后执行。
3. 查询结果可以返回给前端。

### 阶段五：SQL Repair

目标：SQL 出错后可以自动修复。

任务：

1. 捕获数据库错误。
2. 编写 SQL Repair Prompt。
3. 实现最多 3 次修复。
4. 修复后重新校验和执行。

验收标准：

1. 字段名错误可以修复。
2. 表名错误可以修复。
3. GROUP BY 错误可以修复。
4. 修复次数可记录。

### 阶段六：LangGraph 工作流

目标：使用 LangGraph 统一编排 Agent 流程。

任务：

1. 定义 AgentState。
2. 定义各节点函数。
3. 定义条件边。
4. 实现失败修复循环。
5. 输出完整执行状态。

验收标准：

1. Agent 工作流可运行。
2. SQL 失败后进入 Repair。
3. SQL 成功后进入 Answer Generator。

### 阶段七：前端展示

目标：完成可展示页面。

任务：

1. 实现自然语言输入框。
2. 展示生成 SQL。
3. 展示查询结果表格。
4. 展示自然语言解释。
5. 展示 SQL 优化建议。

验收标准：

1. 用户可以在页面提交问题。
2. 页面可以展示 SQL 和查询结果。
3. 页面可以展示解释和错误信息。

### 阶段八：SQL Optimizer 与 EXPLAIN ANALYZE

目标：增加 SQL 优化能力。

任务：

1. 实现 EXPLAIN ANALYZE 调用。
2. 解析执行计划。
3. 识别慢查询原因。
4. 生成优化建议。
5. 展示优化前后耗时。

验收标准：

1. 系统能返回执行计划。
2. 系统能识别基础性能问题。
3. 前端能展示优化建议。

### 阶段九：ChromaDB Schema Retriever，可选

目标：提升复杂数据库场景下的表字段选择能力。

任务：

1. 将表说明、字段说明、指标定义写入 ChromaDB。
2. 实现 Schema Retriever。
3. 替代全量 Schema 输入。
4. 测试复杂问题下的检索效果。

验收标准：

1. 用户问题能检索到相关表和字段。
2. 生成 SQL 的表字段选择错误减少。

### 阶段十：评估与文档

目标：让项目适合简历展示。

任务：

1. 构建 30 到 50 条测试问题。
2. 编写评估脚本。
3. 统计核心指标。
4. 完善 README。
5. 准备项目截图。
6. 整理简历表达。

验收标准：

1. 有完整 README。
2. 有评估结果。
3. 有前端截图。
4. 项目可以一键启动。

---

## 17. README 结构建议

```markdown
# Data Analyst Agent

## 项目简介

## 核心功能

## 技术栈

## 系统架构

## Agent 工作流

## 数据库设计

## API 文档

## 项目运行

## 示例问题

## 效果展示

## SQL 安全机制

## SQL 修复机制

## SQL 优化机制

## 评估结果

## 后续优化
```

---

## 18. 示例业务问题

### 18.1 简单统计

1. 查询 2024 年订单总数。
2. 查询所有商品类别的数量。
3. 查询注册用户数量。

### 18.2 聚合分析

1. 统计 2024 年每个月的销售额。
2. 统计不同地区的客户数量。
3. 统计每个商品类别的销售额。

### 18.3 排名分析

1. 找出销售额最高的前 10 个商品。
2. 找出订单数最多的前 10 个客户。
3. 找出退款金额最高的前 5 个商品类别。

### 18.4 复杂分析

1. 统计不同地区的复购率。
2. 分析各商品类别的退款率。
3. 计算 2024 年每个月销售额同比增长率。
4. 计算不同支付方式的平均订单金额。
5. 分析高价值客户的地区分布。

---

## 19. 简历表达建议

### 19.1 项目标题

**Data Analyst Agent：自然语言驱动的数据库分析与 SQL 优化系统**

### 19.2 技术栈

Python, FastAPI, LangGraph, SQLGlot, PostgreSQL, DuckDB, Vue 3, Element Plus, ECharts, ChromaDB, Docker

### 19.3 项目描述

1. 基于 FastAPI、Vue 和 LangGraph 构建自然语言驱动的数据分析 Agent 系统，实现从用户问题到 SQL 生成、查询执行、结果解释和图表展示的完整流程。
2. 基于 SQLGlot 实现 SQL AST 安全校验模块，支持危险语句拦截、只读查询约束、自动 LIMIT 注入和查询超时控制，避免直接执行大模型生成的高风险 SQL。
3. 设计 SQL 执行反馈修复机制，捕获数据库错误并结合 Schema 上下文自动修复字段不存在、表名错误、GROUP BY 错误等问题。
4. 集成 EXPLAIN ANALYZE 执行计划分析，识别全表扫描、低效 JOIN、排序成本过高和索引缺失等问题，并生成 SQL 优化建议。
5. 构建测试问题集，评估 SQL 执行成功率、修复成功率、平均修复次数、危险 SQL 拦截率和优化前后查询耗时变化。

---

## 20. 风险与解决方案

### 20.1 LLM 生成 SQL 不稳定

解决方案：

1. 使用结构化 JSON 输出。
2. 限制 SQL 类型。
3. 提供明确 Schema。
4. 引入 SQL Guard。
5. 引入 SQL Repair。

### 20.2 SQL 存在安全风险

解决方案：

1. 只读数据库账号。
2. SQLGlot AST 校验。
3. 危险语句黑名单。
4. 只允许 SELECT / WITH。
5. 查询超时和 LIMIT。

### 20.3 表字段选择错误

解决方案：

1. 第一版使用完整 Schema。
2. 第二版使用 ChromaDB 做 Schema Retriever。
3. 增加字段说明和业务指标定义。

### 20.4 项目容易被认为是 Demo

解决方案：

1. 加入 SQL 安全校验。
2. 加入 SQL 自动修复。
3. 加入执行计划分析。
4. 加入 SQL 优化建议。
5. 加入测试集和评估指标。
6. 完善 README 和项目截图。

---

## 21. 当前推荐开发顺序

建议按照以下顺序开发：

```text
1. 数据库设计与模拟数据
2. FastAPI 后端骨架
3. Schema Loader
4. SQL Guard
5. SQL Executor
6. SQL Generator
7. SQL Repair
8. LangGraph 工作流
9. Vue 前端展示
10. EXPLAIN ANALYZE 与 SQL Optimizer
11. ChromaDB Schema Retriever
12. 评估脚本与 README
```

---

## 22. 第一周任务清单

### Day 1

- [ ] 创建 Git 仓库。
- [ ] 创建项目目录结构。
- [ ] 编写 `docs/project_requirement.md`。
- [ ] 编写 `docs/database_design.md`。
- [ ] 编写 `docs/api_design.md`。
- [ ] 编写 `docs/agent_workflow.md`。

### Day 2

- [ ] 编写 `database/init.sql`。
- [ ] 编写 `database/seed_data.py`。
- [ ] 创建 DuckDB 或 PostgreSQL 数据库。
- [ ] 手写 SQL 验证数据可查询。

### Day 3

- [ ] 搭建 FastAPI 后端。
- [ ] 实现 `GET /api/schema`。
- [ ] 实现 mock 版 `POST /api/chat/query`。
- [ ] 用 Swagger UI 测试接口。

### Day 4

- [ ] 实现 `schema_loader.py`。
- [ ] 实现 `sql_guard.py`。
- [ ] 编写 SQL Guard 单元测试。
- [ ] 验证危险 SQL 能被拦截。

### Day 5

- [ ] 实现 `query_runner.py`。
- [ ] 实现 SQL 执行耗时统计。
- [ ] 实现 SQL 执行错误捕获。
- [ ] 串联 SQL Guard 和 SQL Executor。

### Day 6

- [ ] 接入 LLM API。
- [ ] 实现 SQL Generator。
- [ ] 约束 LLM 输出 JSON。
- [ ] 测试 5 个自然语言问题。

### Day 7

- [ ] 实现 SQL Repair 初版。
- [ ] 测试字段错误、表名错误、GROUP BY 错误。
- [ ] 整理第一周 README。
- [ ] 提交 Git commit。

---

## 23. 版本规划

### v0.1

- FastAPI 后端骨架。
- 数据库建表和模拟数据。
- Schema Loader。
- SQL Guard。
- SQL Executor。

### v0.2

- SQL Generator。
- SQL Repair。
- LangGraph 工作流。
- 查询结果解释。

### v0.3

- Vue 前端页面。
- SQL 展示。
- 查询结果表格。
- 图表展示。

### v0.4

- EXPLAIN ANALYZE。
- SQL Optimizer。
- 优化建议展示。

### v0.5

- ChromaDB Schema Retriever。
- 指标定义检索。
- 历史 SQL 样例检索。

### v1.0

- Docker Compose 一键部署。
- 完整 README。
- 评估脚本。
- 项目截图。
- 简历版项目描述。

---

## 24. 最终交付物

项目完成后应包含以下内容：

1. 可运行的前后端项目。
2. 可初始化的数据库脚本。
3. 可生成模拟数据的脚本。
4. SQL 安全校验模块。
5. SQL 执行与修复模块。
6. SQL 优化建议模块。
7. 前端展示页面。
8. 测试问题集。
9. 评估报告。
10. README 文档。
11. Docker Compose 部署文件。
12. 简历项目描述。

---

## 25. 项目核心判断标准

本项目最终是否不像 Toy Project，取决于以下几点是否完成：

1. 是否有 SQL 安全校验。
2. 是否有执行反馈修复机制。
3. 是否有执行计划分析。
4. 是否有 SQL 优化建议。
5. 是否有测试集和评估指标。
6. 是否有完整前后端和部署文档。

如果只完成自然语言生成 SQL，则项目偏 Demo。

如果完成 SQL 生成、校验、执行、修复、优化和评估闭环，则可以作为较完整的实习项目展示。

