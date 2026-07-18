# Data Analyst Agent 面试讲述稿

这份文档用于面试前快速复习，重点回答三个问题：项目解决了什么、技术上难在哪里、你怎么证明它可靠。

## 30 秒介绍

Data Analyst Agent 是一个自然语言驱动的数据分析系统。用户用中文或英文提出业务问题后，系统会先做认证和安全意图检查，再解析结构化分析意图并进行 Schema Grounding；明显模糊且缺关键槽位的问题会在 SQL 生成前主动澄清，明确问题则结合多轮上下文调用 OpenAI 兼容 LLM API 生成 DuckDB SQL，再经过 SQLGlot AST 安全校验、YAML 数据权限策略、行级 SQL 过滤、执行、修复、优化和答案生成。

这个项目的重点不是简单调用大模型写 SQL，而是把 LLM 输出放进一个可控工程闭环：危险意图提前拦截，SQL 执行前做 AST 安全校验和角色权限校验，失败能修复，结果能解释，审计能展示，评测和 CI 能证明关键路径稳定。

## 简历写法

可以写成：

> 构建自然语言驱动的数据分析 Agent，基于 FastAPI + LangGraph + DuckDB + OpenAI 兼容 LLM API 实现 NL2SQL、多轮追问、分层意图解析、Schema Grounding、主动澄清、SQL 安全校验、YAML 数据权限策略、行级 SQL 过滤、执行失败自动修复、SQL 优化建议、LLM 调用可观测性和结构化审计报告；用 65 条结构化评测、6 条权限回归评测、15 条可执行核心路径、717 个后端测试、58 个前端单测、17 个 E2E 和 GitHub Actions 质量门禁证明关键链路稳定。

## 技术架构

核心链路：

```text
用户问题
  -> Auth (JWT / API Key)
  -> Intent Guard
  -> Analysis Intent Parser
  -> Schema Grounding
  -> Clarification Decision
  -> SessionStore / Conversation Context
  -> Schema Loader
  -> SQL Generator (LLM structured JSON)
  -> SQL Guard (SQLGlot AST)
  -> Data Permission Guard (YAML policy + Role/Table/Column + Row Filter)
  -> Permission Observability (permission_checked / allowed / row_filters_applied)
  -> AuditReport (身份、LLM、权限、安全事件)
  -> Query Runner (DuckDB / PostgreSQL)
  -> SQL Repair Agent (失败重试)
  -> SQL Optimizer (EXPLAIN)
  -> Answer Generator
  -> FastAPI / Vue 工作台
```

关键模块：

| 模块 | 文件 | 面试可讲点 |
|---|---|---|
| Agent 编排 | `backend/app/agents/graph.py` | LangGraph 节点、条件边、权限阻断、最多 3 次修复重试 |
| Intent Guard | `backend/app/security/intent_guard.py` | LLM 调用前阻断危险意图，fail-closed |
| Analysis Intent | `backend/app/analysis_intent/` | 规则解析 + LLM 解析 + 候选合并，输出结构化指标/维度/过滤/排序 |
| Schema Grounding | `backend/app/agents/grounding.py` | 将业务概念映射到稳定表达式、候选表和 JOIN 路由 |
| Clarification | `backend/app/agents/clarification.py` / `backend/app/agents/session_store.py` | 模糊问题在 SQL 生成前暂停，用 `candidate_id` 恢复任务 |
| SQL Guard | `backend/app/security/sql_guard.py` | AST 安全校验、SELECT/WITH 白名单、LIMIT 注入、危险函数拦截 |
| Data Permission Guard | `backend/app/security/data_permission.py` | 检查最终 SQL AST 的表/字段权限，阻断不执行、不修复 |
| Permission Policy | `backend/app/security/permission_policy.py` / `backend/app/security/data_permissions.yaml` | YAML 策略外部化，admin/analyst/support 权限和行级过滤规则可审计 |
| Audit Report | `backend/app/agents/audit.py` | 汇总身份、LLM 调用、权限检查、安全事件和最终 SQL |
| LLM Observability | `backend/app/services/llm_observability.py` | ContextVar 并发隔离，Token/耗时/成本汇总 |
| SQL Optimizer | `backend/app/agents/sql_optimizer.py` | EXPLAIN、顺序扫描识别、结果规模和 `SELECT *` 建议 |
| Evaluation Runner | `backend/evaluation/evaluator.py` | 32 条 NL2SQL case 量化生成、执行、修复和安全表现 |
| Intent Evaluation | `backend/evaluation/intent_evaluator.py` | 37 条危险意图 case 量化提前阻断和误杀 |
| Grounding Evaluation | `backend/evaluation/intent_grounding_evaluator.py` | 7 条 case 量化槽位、Grounding、路由和澄清决策 |
| Permission Evaluation | `backend/evaluation/permission_evaluator.py` | 6 条确定性权限 case 验证允许/阻断、规则 ID、行级过滤、SQL 改写和 admin 对照 |
| Security Audit Export | `backend/evaluation/security_audit_exporter.py` | 汇总 Intent、Grounding、权限、真实评测和质量门禁为 JSON/Markdown 报告 |
| Quality Gate | `backend/evaluation/quality_gate.py` / `.github/workflows/ci.yml` | 基础 CI 跑后端、PostgreSQL、前端单元测试、Playwright 前端 E2E、Docker Compose 配置校验、Docker 镜像构建、后端容器 readiness smoke test、secret scan、确定性评测和权限指标 |
| Audit Panel | `frontend/src/components/AuditPanel.vue` | 前端展示身份、authorization 事件和 permission_observability 权限证据 |
| 前端工作台 | `frontend/src/` | SQL、表格、图表、优化建议、多轮会话和审计事件统一展示 |

## 面试高频追问

### 1. 你这个项目和普通 ChatGPT 生成 SQL 有什么区别？

普通生成 SQL 只解决“生成”问题，这个项目解决的是“生成后的可控执行”。LLM 输出不会直接进数据库，而是经过 Intent Guard、SQL Guard 和 Data Permission Guard 三层治理。执行失败也不是直接返回错误，而是进入 Repair Agent，修复后的 SQL 仍然必须重新经过 Guard 和权限检查。

### 2. 怎么保证 LLM 不会生成危险 SQL？

我没有只靠 prompt 约束，而是在执行前做程序级防护。SQL Guard 使用 SQLGlot 解析 AST，限制单条 `SELECT/WITH/EXPLAIN SELECT`，拦截 DDL/DML、多语句、系统表访问和 DuckDB 文件读取函数，例如 `read_csv_auto('/etc/passwd')`。同时会自动注入 LIMIT，避免大结果集无限返回。

### 3. 怎么证明权限不是只写在 prompt 里？

权限检查发生在 SQL Guard 之后、QueryRunner 之前，输入是 SQLGlot 解析后的最终 SQL AST。`DataPermissionGuard` 提取真实表、字段和别名，再用 YAML 策略做表级、字段级和行级规则检查；阻断时不执行、不进入 Repair、不写入多轮上下文。也就是说，权限不信任自然语言问题，也不信任模型解释，只信任最终 SQL 的 AST。

### 4. 怎么证明行级过滤真的生效？

analyst 查询订单类指标时，权限层会把最终 SQL 改写为带区域范围过滤的 authorized SQL。`audit_report.permission_observability` 会展示 `row_filters_applied=[{"table":"orders","rule_id":"row_filter_region_scope"}]` 和 `authorized_sql_changed=true`；前端安全审计面板也会展示这些字段。对应单测和 E2E 覆盖在 `frontend/tests/components/AuditPanel.test.js` 和 `frontend/e2e/permission-demo.spec.js`。

### 5. 为什么要用 LangGraph？

这个流程不是单次 LLM 调用，而是有条件分支和循环：Intent Guard 通过后进入 `parse_intent -> ground_schema -> assess_clarification`，需要澄清就提前暂停；明确问题才继续生成 SQL。SQL 校验和数据权限校验都通过才执行，执行失败进入修复，修复后重新校验和重新授权，最多重试 3 次。LangGraph 适合表达这种有状态、多节点、可重试的 Agent 工作流，比把逻辑都写在一个函数里更清晰，也更方便测试。

### 6. SQL 修复是怎么做的？

QueryRunner 执行失败时不会直接抛异常，而是返回结构化错误，包括错误类型和错误信息。Repair Agent 会拿到原 SQL、错误信息和 Schema，让 LLM 生成修复 SQL。修复 SQL 不会直接执行，而是重新走 SQL Guard 和 Data Permission Guard，防止修复过程中生成危险语句或越权查询。

### 7. SQL 优化建议是不是 LLM 编的？

当前优化建议不是让 LLM 自由发挥，而是规则化生成。Optimizer 会分析 SQL AST、查询结果规模和 DuckDB `EXPLAIN` 执行计划，例如检测 `SELECT *`、结果达到 LIMIT、执行计划包含顺序扫描，然后给出可解释建议。这样建议更稳定，也方便测试。

### 8. 你怎么证明项目可靠？

当前项目有 717 个后端测试、58 个前端单测、17 个 E2E、65 条结构化评测用例、6 条数据权限回归评测和 15 条可执行核心路径。基础 CI 不依赖真实 LLM secret，会运行 Ruff/ESLint、75% 覆盖率门槛、PostgreSQL migration round trip、前后端测试、Playwright E2E、demo/secure Compose 校验、镜像与 readiness smoke、依赖审计、Secret Scan 和确定性评测。真实模型评测保留在手动 workflow：13/3/5 个分片依次运行且最大并发为 2，每个分片逐 case 原子 checkpoint；最终严格汇总同一 HEAD SHA、Provider、模型和 case pack 哈希后才允许进入质量门禁。

### 9. 安全审计报告有什么用？

安全审计报告解决的是“安全证据可展示”的问题。每次查询会返回 `audit_report`，里面包含用户身份摘要、认证方式、角色、最终 SQL、是否安全、是否执行成功、修复次数、是否自动注入 LIMIT、命中的拦截规则、LLM 调用汇总和权限检查摘要。面试官问“怎么证明危险 SQL 或越权字段被拦截了”时，可以展示结构化事件，而不是只口头说有 Guard。

### 10. 面试现场怎么展示安全审计？

先用 analyst 角色查询销售额，展示行级过滤和 SQL 改写；再查询客户姓名，展示 `block_unauthorized_column` 和 `customers.customer_name`；最后切 admin 证明同一问题可以被授权执行。右侧 AuditPanel 和 `python -m evaluation.security_audit_exporter --write-report` 分别展示在线审计和离线报告。离线报告会在“输入完整性”里明确写出是否未提供真实评测输入；版本交付或面试前复核时可以加 `--fail-on-missing-real-reports` 做严格检查，避免把缺失真实评测报告误当成已通过证据。真实模型 workflow 会保留每个分片的 checkpoint，并在严格汇总后生成绑定 HEAD SHA 的 `security-audit-*.md/json`；缺片 artifact 只能作为失败诊断，不能冒充当前版本通过证据。

### 11. 为什么要做业务语义层？

数据库 Schema 只能告诉模型有哪些表和字段，但不能告诉它“销售额”“退款率”“复购率”这些业务词应该如何计算。语义层把指标和维度定义成机器可读配置，SQL 生成时会把指标表达式、JOIN 关系和默认时间字段一起传给 LLM，降低字段幻觉和业务口径错误。

### 12. 为什么要做结果正确性评测？

执行成功只说明 SQL 合法，不代表业务口径正确。模型可能选错 JOIN、在一对多 JOIN 后重复聚合、使用错误分母，或返回不稳定列名。结果正确性评测用人工审核参考 SQL、固定断言和确定性比较器验证列结构、结果值、排序和核心指标。首轮真实基线正是靠它发现了商品类别销售额被重复计算的问题。

### 13. 你怎么单独证明 SQL Repair 有效？

完整 Agent 流程不一定稳定生成错误 SQL，因此我增加了独立故障注入评测器。它使用 6 条能够通过 Guard、但会在 DuckDB 中确定性失败的 SQL，覆盖错误字段、错误表、缺失 JOIN 和数据库方言问题，再依次验证真实错误、Repair、修复后 Guard、执行和意图保持。首轮端到端修复成功率为 `5/6`，根据季度格式失败样本补充 DuckDB prompt 约束和回归测试后，相同用例复测为 `6/6`。

### 14. 你怎么衡量 LLM 性能和成本？

我在 LLM API 边界读取 usage，并记录每次逻辑调用的节点、模型、Token、耗时和 API 尝试次数。因为客户端是全局单例，我使用 `ContextVar` 隔离并发异步请求，再通过 LangGraph state 跨节点汇总到 `audit_report.llm_observability`。成本单价用环境变量配置，未配置时成本字段保持空值，不伪造数字。

### 15. 主动澄清是怎么闭环的？

当问题明显模糊且缺少关键指标，或规则/LLM 意图候选冲突时，AgentGraph 会在 SQL 生成前暂停，不加载 Schema、不生成 SQL，也不访问数据库。API 返回 `status=clarification_required` 和稳定候选 `candidate_id`；前端点击候选后，后端用 SessionStore 找回冻结的原问题，把候选归一化后重新经过 Intent Guard，再继续完整分析链路。

### 16. 项目目前还有什么不足？

可以坦诚说：

- SQL 优化建议仍是规则化第一版，还没有做复杂成本模型。
- LLM 指标目前在请求和评测报告中可见，还没有接入长期时序监控。
- 前端图表适合演示常见分析，不是完整 BI 拖拽配置器。
- 后续可以补多租户持久化策略、更多数据库方言、公开数据集泛化评测和长期指标告警。
- `graph.py`、`llm_service.py` 和权限模块仍偏大；v1.8 已明确按图编排/节点实现、HTTP transport/结构化解析、策略编译/SQL 改写拆分，但面试冻结版不做无业务收益的大重构。

## 演示脚本

本地启动后端：

```bash
cd backend
pip install -r requirements.txt
python ../database/seed_data.py
uvicorn app.main:app --reload
```

另开终端启动前端：

```bash
cd frontend
npm install
npm run dev
```

权限演示需要 `.env` 中开启：

```bash
JWT_SECRET=dev-demo-secret-change-me-32-bytes
AUTH_DEMO_ENABLED=true
```

推荐演示顺序：

1. 运行 `python scripts/interview_demo_preflight.py --strict` 做面试演示预检，确认 `.env`、后端 readiness 和前端页面状态。
2. 运行 `cd backend && python -m evaluation.core_path_runner`，让 `backend/evaluation/cases/core_path_cases.yaml` 的 15 条场景真实经过 Agent、Guard、Grounding、权限、数据库和会话链路。
3. 用 `Analyst` 身份查询 `统计 2024 年每个月的销售额`，观察答案、图表和“数据权限”区里的 `row_filter_region_scope`。
4. 用同一身份查询 `分析各商品类别的退款率`，展示退款率业务口径和图表结果。
5. 继续提问 `只看订单数，按月份升序排列`，展示多轮追问会复用上一轮上下文。
6. 用同一身份查询 `列出客户姓名和注册日期`，观察阻断答案、`block_unauthorized_column` 和 `customers.customer_name`。
7. 切换 `Admin` 后重复客户姓名问题，证明权限策略不是简单禁用功能，而是按角色授权。
8. 输入 `删除订单表`，展示危险意图在执行前被拦截。
9. 输入模糊问题如 `帮我分析一下`，展示主动澄清候选，再点击候选恢复执行。
10. 运行 `cd backend && python -m evaluation.security_audit_exporter --write-report`，展示可归档的安全审计 JSON/Markdown；如果要做严格交付检查，补齐真实评测报告后加 `--fail-on-missing-real-reports`。
11. 运行 `python scripts/interview_evidence.py --run-id <github_run_id>`，生成本地验证、远端真实模型 artifact 下载和 `security-audit-*.md/json` 检查清单。

核心路径场景记录在 `backend/evaluation/cases/core_path_cases.yaml`。面试前可运行 `cd backend && python -m evaluation.core_path_runner`，确认 15 条场景执行成功且 surface 完整率为 100%；这份报告不保存完整结果行。

## 技术亮点总结

- **安全**：不信任 LLM 输出，所有 SQL 执行前都走 Intent Guard、AST SQL Guard 和角色级数据权限 Guard。
- **闭环**：生成、校验、授权、执行、修复、优化、回答是一条完整 Agent pipeline。
- **权限治理**：YAML 策略、字段阻断、行级过滤、权限观测和前端审计展示形成闭环。
- **可解释**：优化建议来自规则和执行计划，不是纯 LLM 幻觉。
- **可评测**：固定 NL2SQL、Repair、Intent、Grounding、权限和结果正确性基准分别量化生成、安全、修复、意图理解、授权和业务口径。
- **证据可恢复**：真实长评测按固定矩阵分片运行，逐 case 原子 checkpoint；严格汇总拒绝缺片、重复 case 和来源不一致。
- **可澄清**：明显模糊的分析请求在 SQL 生成前暂停，通过稳定候选 ID 恢复原任务。
- **边界清晰**：DuckDB 用固定脚本重建，PostgreSQL 才走 Alembic；secure profile 配置不完整时 readiness fail-closed，真实模型报告必须绑定当前 HEAD SHA。
- **可追问**：基于 session_id 保存轻量上下文，支持连续分析。
- **可审计**：结构化 audit_report 展示身份摘要、SQL 安全判断、权限决策、LLM 调用和执行过程。
- **可验证**：本地测试、确定性评测、CI quality gate 和安全审计导出互相补强。
- **可展示**：前端工作台把 SQL、结果、图表、答案、优化建议和安全审计放在同一个分析界面。
