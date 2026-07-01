# Data Analyst Agent 简历项目包装包

这份文档用于投简历、准备面试和现场演示。它比 `docs/interview_guide.md` 更短，更偏结果表达和证据索引。

## 项目定位

一句话：这是一个企业级 NL2SQL Data Analyst Agent，把自然语言问数从“生成 SQL”推进到“可控执行、可修复、可评测、可审计、可权限治理”的工程闭环。

## 简历 Bullet

### Agent / AI 应用方向

- 设计并实现基于 FastAPI + LangGraph 的 Data Analyst Agent，覆盖 Intent Guard、分层意图解析、Schema Grounding、主动澄清、SQL 生成、SQLGlot AST 安全校验、权限治理、SQL Repair、优化建议和答案生成。
- 构建 65 条结构化评测、5 条权限回归评测和安全审计导出链路，将 NL2SQL、危险意图、Schema Grounding、结果正确性、Repair 和权限安全纳入可复现质量门禁。
- 接入 LLM 调用可观测性，按请求汇总模型、Token、耗时、重试和成本可用性，并在审计报告中展示。

### 后端工程方向

- 在 FastAPI + SQLAlchemy + DuckDB/PostgreSQL 双后端上实现自然语言查询 API、SSE 流式进度、JWT/API Key 认证、速率限制、结构化错误和安全审计报告。
- 使用 SQLGlot AST 实现 SELECT/WITH 白名单、危险函数拦截、系统表拦截、自动 LIMIT 注入、角色级表/字段权限和 analyst 行级 SQL 过滤。
- 通过 GitHub Actions 运行后端测试、PostgreSQL 测试、前端单元测试、Playwright 前端 E2E、Docker Compose 配置校验、Docker 镜像构建、后端容器 readiness smoke test、tracked-file secret scan、确定性评测和 quality gate，避免真实 LLM secret 进入普通 CI。

### 简历短版

- Data Analyst Agent：FastAPI + LangGraph + DuckDB + Vue3 实现企业级 NL2SQL 问数系统，支持多轮追问、主动澄清、SQL Repair、SQL 优化、三层安全治理、权限审计、573 个后端测试、54 个前端单测、17 个 E2E 和 500+ 自动化测试。

## 30 秒介绍

Data Analyst Agent 是一个自然语言驱动的数据分析 Agent。用户输入中文业务问题后，系统会经过 Intent Guard、结构化意图解析、Schema Grounding、SQL 生成、SQL Guard、数据权限 Guard、执行、Repair、优化和答案生成。它的重点不是“让模型写 SQL”，而是把模型输出放进可控闭环：危险意图提前拦截，SQL 执行前做 AST 安全校验和角色权限校验，失败能修复，结果能解释，评测和 CI 能证明关键链路稳定。

## 90 秒介绍

这个项目面向电商数据分析场景，后端用 FastAPI 和 LangGraph 编排 12 节点 Agent 工作流，前端用 Vue3 展示自然语言输入、SQL、图表、结果表、优化建议和审计事件。技术上我重点解决三件事：第一是可控生成，LLM 不直接连数据库，生成 SQL 必须经过 SQLGlot AST Guard，只允许安全查询并自动注入 LIMIT；第二是企业权限治理，Data Permission Guard 基于 YAML 策略检查 admin/analyst/support 的表字段权限，并能对 analyst 订单查询做行级 SQL 改写；第三是可验证质量，我做了 NL2SQL、危险意图、Repair、结果正确性、Grounding、权限评测和安全审计导出，CI 中运行不依赖真实 LLM 的确定性门禁，并覆盖前端单元测试、Playwright 前端 E2E、Docker Compose 配置校验、Docker 镜像构建和后端容器 readiness smoke test。

## STAR 故事

### 安全闭环

- Situation：LLM 生成 SQL 如果直接执行，可能出现 DDL/DML、系统表访问、文件读取或越权字段查询。
- Task：把 NL2SQL 从 demo 变成可控执行系统。
- Action：加入 Intent Guard、SQLGlot AST SQL Guard、Data Permission Guard、权限阻断不进入 Repair、不写入多轮上下文，并把事件汇总到 `audit_report`。
- Result：危险意图、危险 SQL、越权字段和行级权限都有确定性测试、评测和前端审计展示。

### 结果正确性

- Situation：SQL 执行成功不代表业务结果正确，模型可能在 JOIN 后重复聚合或使用错误口径。
- Task：证明系统不是只追求执行成功。
- Action：新增人工审核黄金 SQL、结果比较器和结果正确性评测，暴露并修复 5/10 到 10/10 的口径问题。
- Result：面试时可以讲清楚“生成可执行 SQL”和“生成正确业务结果”的区别。

### 权限治理

- Situation：普通 SQL Guard 只能防危险语句，不能判断不同角色能看哪些业务字段。
- Task：实现接近企业内部数据平台的角色权限治理。
- Action：引入 YAML 权限策略、admin/analyst/support 角色、字段阻断、analyst 行级过滤、`permission_observability`、权限评测和 CI quality gate。
- Result：前端能演示 analyst 被行级过滤、越权字段被阻断、admin 被允许，同一能力也能用离线报告导出。

## 演示检查清单

- 启动后端：`cd backend && uvicorn app.main:app --reload`
- 启动前端：`cd frontend && npm run dev`
- 开启演示登录：`.env` 中设置 `JWT_SECRET=dev-demo-secret` 和 `AUTH_DEMO_ENABLED=true`
- Analyst 查询：`统计 2024 年每个月的销售额`，观察 `row_filter_region_scope`
- Analyst 越权：`列出客户姓名和注册日期`，观察 `block_unauthorized_column` 和 `customers.customer_name`
- Admin 对照：切换 `Admin` 后重复客户姓名问题
- 离线审计：`cd backend && python -m evaluation.security_audit_exporter --write-report`

## 证据索引

| 亮点 | 代码 | 测试/评测 | 演示证据 |
|---|---|---|---|
| LangGraph 工作流 | `backend/app/agents/graph.py` | `backend/tests/test_agent_graph.py` | README 架构图 |
| SQL 安全 | `backend/app/security/sql_guard.py` | `backend/tests/test_sql_guard.py` | `audit_report.blocked_rules` |
| 数据权限 | `backend/app/security/data_permission.py` | `backend/tests/test_data_permission_guard.py` | AuditPanel 数据权限区 |
| 权限策略 | `backend/app/security/permission_policy.py` / `backend/app/security/data_permissions.yaml` | `backend/tests/test_permission_policy.py` | YAML 策略文件 |
| 权限评测 | `backend/evaluation/permission_evaluator.py` | `backend/tests/test_permission_evaluator.py` | quality gate 权限指标 |
| 安全审计导出 | `backend/evaluation/security_audit_exporter.py` | `backend/tests/test_security_audit_exporter.py` | Markdown/JSON 报告 |
| 前端演示 | `frontend/src/components/AuditPanel.vue` | `frontend/tests/components/AuditPanel.test.js` / `frontend/e2e/permission-demo.spec.js` | analyst/admin 演示 |
| CI / 部署证据 | `.github/workflows/ci.yml` / `docker-compose.yml` | `backend/tests/test_workflow_files.py` | 前端单测、Playwright 前端 E2E、Docker Compose 配置校验、Docker 镜像构建、后端容器 readiness smoke test |

## 边界说明

- 已完成：NL2SQL 闭环、多轮追问、主动澄清、SQL Repair、结果正确性评测、权限治理、行级过滤、CI 质量门禁、安全审计导出和前端审计展示。
- 后续扩展：多租户持久化策略、更多数据库方言、长期指标监控、公开数据集泛化评测、复杂执行计划成本模型。
