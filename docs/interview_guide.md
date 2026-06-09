# Data Analyst Agent 面试讲述稿

这份文档用于面试前快速复习，重点回答三个问题：项目解决了什么、技术上难在哪里、你怎么证明它可靠。

## 30 秒介绍

Data Analyst Agent 是一个自然语言驱动的数据分析系统。用户用中文或英文提出业务问题，系统会读取数据库 Schema 和业务语义层，结合多轮会话上下文调用 Qwen 生成 DuckDB SQL，再经过 SQLGlot AST 安全校验，执行查询，失败时自动修复 SQL，成功后生成自然语言解释、图表、SQL 优化建议和安全审计报告。

这个项目的重点不是简单调用大模型，而是把 LLM 生成 SQL 放进一个可控的工程闭环：有安全 Guard、有失败修复、有执行计划分析、有前后端联调，也有自动化测试证明关键路径能稳定运行。

## 简历写法

可以写成：

> 构建自然语言驱动的数据分析 Agent，基于 FastAPI + LangGraph + DuckDB + Qwen API 实现 NL2SQL、多轮追问、SQL 安全校验、执行失败自动修复、结果解释、SQL 优化建议、离线评测报告和安全审计报告；使用 SQLGlot AST 拦截危险 SQL、系统表访问和 DuckDB 文件读取函数，后端 98 个 pytest 用例覆盖 Guard、Agent 工作流、LLM service、Schema loader、语义层、评测体系、多轮上下文、审计报告和 QueryRunner。

## 技术架构

核心链路：

```text
用户问题
  -> SessionStore / Conversation Context
  -> Schema Loader
  -> SQL Generator (Qwen)
  -> SQL Guard (SQLGlot AST)
  -> AuditReport (安全审计事件)
  -> Query Runner (DuckDB)
  -> SQL Repair Agent (失败重试)
  -> SQL Optimizer (EXPLAIN)
  -> Answer Generator (Qwen)
  -> FastAPI / Vue 工作台
```

关键模块：

| 模块 | 文件 | 面试可讲点 |
|---|---|---|
| Agent 编排 | `backend/app/agents/graph.py` | LangGraph 节点、条件边、最多 3 次修复重试 |
| SQL Guard | `backend/app/security/sql_guard.py` | AST 安全校验、LIMIT 注入、危险函数拦截 |
| Audit Report | `backend/app/agents/audit.py` | 汇总生成、校验、修复、执行过程中的安全证据 |
| SQL Optimizer | `backend/app/agents/sql_optimizer.py` | EXPLAIN、顺序扫描识别、规则化建议 |
| Query Runner | `backend/app/db/query_runner.py` | 结构化返回执行结果和错误信息 |
| LLM Service | `backend/app/services/llm_service.py` | Qwen API、JSON 输出解析、重试逻辑 |
| Conversation Context | `backend/app/agents/conversation_context.py` | 把上一轮问题、SQL、列名和答案压缩为追问上下文 |
| Session Store | `backend/app/agents/session_store.py` | 基于 session_id 保存最近几轮分析摘要 |
| Evaluation Runner | `backend/evaluation/evaluator.py` | 32 条固定 case 量化生成、执行、修复和安全表现 |
| 前端工作台 | `frontend/src/` | SQL、表格、图表、优化建议、多轮会话和审计事件统一展示 |

## 面试高频追问

### 1. 你这个项目和普通 ChatGPT 生成 SQL 有什么区别？

普通生成 SQL 只解决“生成”问题，这个项目解决的是“生成后的可控执行”。LLM 输出不会直接进数据库，而是经过 SQL Guard 校验，只允许安全查询。执行失败后也不是直接返回错误，而是进入修复 Agent，修复后的 SQL 仍然必须重新经过 Guard。

### 2. 怎么保证 LLM 不会生成危险 SQL？

我没有只靠 prompt 约束，而是在执行前做了程序级防护。SQL Guard 使用 SQLGlot 解析 AST，限制单条 `SELECT/WITH/EXPLAIN SELECT`，拦截 DDL/DML、多语句、系统表访问和 DuckDB 文件读取函数，例如 `read_csv_auto('/etc/passwd')`。同时会自动注入 LIMIT，避免大结果集无限返回。

### 3. 为什么要用 LangGraph？

这个流程不是单次 LLM 调用，而是有条件分支和循环：校验通过才执行，执行失败进入修复，修复后重新校验，最多重试 3 次。LangGraph 适合表达这种有状态、多节点、可重试的 Agent 工作流，比把逻辑都写在一个函数里更清晰，也更方便测试。

### 4. SQL 修复是怎么做的？

QueryRunner 执行失败时不会直接抛异常，而是返回结构化错误，包括错误类型和错误信息。Repair Agent 会拿到原 SQL、错误信息和 Schema，让 Qwen 生成修复 SQL。修复 SQL 不会直接执行，而是重新走 SQL Guard，防止修复过程中生成危险语句。

### 5. SQL 优化建议是不是 LLM 编的？

当前优化建议不是让 LLM 自由发挥，而是规则化生成。Optimizer 会分析 SQL AST、查询结果规模和 DuckDB `EXPLAIN` 执行计划，例如检测 `SELECT *`、结果达到 LIMIT、执行计划包含顺序扫描，然后给出可解释建议。这样建议更稳定，也方便测试。

### 6. 你怎么证明项目可靠？

后端有 pytest 自动化测试，目前 98 个用例通过。测试覆盖 SQL Guard、安全边界、AgentGraph 正常路径、Guard 拒绝直接终止、执行失败修复、重试耗尽、LLM JSON 解析、Schema Loader、Semantic Loader、Evaluation Runner、ReportWriter、Conversation Context、SessionStore、AuditReport、Query API、QueryRunner 和 SQL Optimizer。为了避免依赖本机真实数据库，pytest 使用隔离 DuckDB 测试库。

### 7. 项目目前还有什么不足？

可以坦诚说：

- SQL 优化建议还是规则化第一版，还没有做成本估算和复杂执行计划解析。
- 前端图表自动选择比较基础，目前适合展示趋势和类别对比，不是完整 BI 配置器。
- LLM Service 的重试策略还有优化空间，例如对 429 和 5xx 做更细粒度处理。
- 后续可以加入查询历史持久化、权限控制、更多数据库方言和 CI。

### 8. 为什么要做业务语义层？

数据库 Schema 只能告诉模型有哪些表和字段，但不能告诉它“销售额”“退款率”“复购率”这些业务词应该如何计算。语义层把这些指标和维度定义成机器可读配置，SQL 生成时会把指标表达式、JOIN 关系和默认时间字段一起传给 LLM，降低字段幻觉和业务口径错误。

### 9. 为什么要做 NL2SQL 评测体系？

单元测试能证明代码逻辑没坏，但不能量化“自然语言问题生成 SQL”的效果。我做了 32 条固定评测 case，覆盖电商指标、维度拆分、安全拦截和修复诱导问题。每次升级后都可以运行 `python -m evaluation.evaluator`，生成 Markdown/JSON 报告，对比生成成功率、执行成功率、修复成功率和安全预期命中率。

### 10. 多轮分析是怎么实现的？

API 请求可以带 `session_id`。AgentGraph 开始前会从内存版 SessionStore 读取最近几轮分析摘要，包括上一轮问题、最终 SQL、结果列、行数和答案摘要，然后把这些内容作为 `conversation_context` 传给 SQL Generator。这样用户第二轮说“按地区拆一下”时，LLM 能继承上一轮的销售额指标和时间范围。为了避免上下文污染，我没有保存完整 rows，只保留可解释摘要，并限制最近轮数。

### 11. 安全审计报告有什么用？

安全审计报告解决的是“安全证据可展示”的问题。每次查询会返回 `audit_report`，里面包含最终 SQL、是否安全、是否执行成功、修复次数、是否自动注入 LIMIT、命中的拦截规则，以及生成、Guard 校验、修复、执行、答案生成等事件。这样面试官问“你怎么证明危险 SQL 被拦截了”时，不只是口头说 Guard，而是能展示结构化事件。

## 演示脚本

本地启动：

```bash
cd backend
pip install -r requirements.txt
python ../database/seed_data.py
uvicorn app.main:app --reload
```

另开终端：

```bash
cd frontend
npm install
npm run dev
```

推荐演示问题：

- `统计 2024 年每个月的订单数量`
- `按地区拆一下`
- `找出销售额最高的 5 个商品`
- `统计各地区的客户数量`
- `分析各商品类别的退款率`

演示时讲解顺序：

1. 用户输入自然语言问题。
2. 展示生成 SQL 和安全状态。
3. 展示查询结果表格和图表。
4. 展示自然语言解释。
5. 展示优化建议。
6. 打开测试结果，说明后端关键逻辑有自动化覆盖。
7. 运行评测命令，展示固定 case 集和 Markdown 评测报告。
8. 用同一个 `session_id` 连续提问，展示多轮追问会复用上一轮上下文。
9. 展示接口响应里的 `audit_report`，说明 LIMIT 注入和危险 SQL 拦截证据。

## 技术亮点总结

- **安全**：不信任 LLM 输出，所有 SQL 执行前都走 AST Guard。
- **闭环**：生成、校验、执行、修复、优化、回答是一条完整 Agent pipeline。
- **可解释**：优化建议来自规则和执行计划，不是纯 LLM 幻觉。
- **可评测**：固定 NL2SQL case 集能量化生成、执行、修复和安全表现。
- **可追问**：基于 session_id 保存轻量上下文，支持连续分析。
- **可审计**：结构化 audit_report 展示 SQL 安全判断和执行过程。
- **可验证**：后端测试隔离真实数据库，能稳定一键运行。
- **可展示**：前端工作台把 SQL、结果、图表、答案、优化建议放在同一个分析界面。
