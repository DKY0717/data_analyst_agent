# Data Analyst Agent 全新学习课程 v2 实施计划

> 对应设计：`docs/superpowers/specs/2026-07-20-data-analyst-agent-course-v2-design.md`
>
> 首版源码基线：`8dffc1d76c514c7efe1b6e642ea1880a81989109`
>
> 新课程目录：`user_docs/data-analyst-agent-course-v2/`

## 1. 实施原则

- 新课程完全独立，不修改、不链接、不复制 `user_docs/data-analyst-agent-course/`。
- 当前仓库源码、测试和实际运行证据是唯一实现事实来源。
- 全部解释性文字使用 Markdown 引用块；代码、命令、配置和日志使用带语言标识的代码块。
- 不整文件复制生产代码，只保留知识点所需片段，并标注真实文件与符号。
- 每章必须完整包含设计规定的十四项教学结构，不创建空章节或占位章节。
- 每条命令注明工作目录、网络要求、真实模型要求和费用边界。
- 真实模型证据注明提交、provider、model、run 和结果完整性；缺失证据不得描述为通过。
- 所有日常学习都提供无需外部 LLM 的确定性路径；真实 LLM 只作为主动选择的扩展验证。
- 每个任务完成后依次进行规格符合性审查和内容质量审查，验证通过后独立提交。
- 工作树中已有的 `logs/work-diary.md` 和 `.tmp/` 改动不修改、不暂存、不提交。

## 2. 统一章节文件结构

每章使用以下结构，编号可按章号调整：

```markdown
# 第N章 章节名称

> 基线、预计时间和本章定位。

## N.1 学习目标
## N.2 前置知识
## N.3 为什么需要这一模块
## N.4 输入、输出与依赖
## N.5 执行流程
## N.6 当前代码地图
## N.7 关键代码理解
## N.8 最小动手运行
## N.9 故障注入实验
## N.10 调试路径与常见误判
## N.11 独立编码练习
## N.12 测试或评测验证
## N.13 面试复述题
## N.14 掌握度检查与下一章
```

允许在上述主节下增加三级和四级标题，但不得删除主节。章节中的“关键代码理解”至少说明模块职责、输入、输出、核心分支和易错点；“故障注入实验”必须可恢复且不得破坏用户数据。

## 3. Task 1：课程骨架、导航和契约测试

### 新建目录和总览文件

- `user_docs/data-analyst-agent-course-v2/README.md`
- `user_docs/data-analyst-agent-course-v2/_sidebar.md`
- `user_docs/data-analyst-agent-course-v2/index.html`
- `user_docs/data-analyst-agent-course-v2/CURRENT-CODE-MAP.md`
- `user_docs/data-analyst-agent-course-v2/STUDY-CHECKLIST.md`
- `user_docs/data-analyst-agent-course-v2/INTERVIEW-QUESTIONS.md`
- `user_docs/data-analyst-agent-course-v2/TROUBLESHOOTING.md`
- `user_docs/data-analyst-agent-course-v2/CHANGELOG.md`

### 新建或修改测试

- 新建 `backend/tests/test_learning_course_v2_docs.py`。
- 不修改旧课程契约测试的语义；新测试只负责 v2。

### 内容要求

- README 给出适合 Python/SQL 初级学习者的八周路线、三层毕业目标和课程使用方法。
- 侧边栏和首页列出七部分三十二章的稳定链接。
- Docsify 页面启用搜索、复制代码、分页、语法高亮和 Mermaid。
- Code Map 建立章节到源码以及核心区域到章节的双向映射。
- Checklist 按八周和每日学习时段记录阅读、运行、故障、编码、复述与证据。
- Interview Questions 按基础、Agent、安全、权限、质量和项目边界分组。
- Troubleshooting 首版覆盖工作目录、依赖、数据库、端口、LLM、前端、Docker 和 CI。
- Changelog 记录基线提交、创建日期、独立课程策略和后续同步流程。

### 契约测试要求

- 检查八个总览文件和三十二个章节目标路径。
- 检查 README、侧边栏和章节路径集合一致。
- 检查章节主结构、代码围栏、占位词和敏感信息模式。
- 检查 Code Map 引用的核心本地路径存在。
- 检查所有总览文件使用同一基线提交。
- 检查旧课程目录未被新课程引用。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py -q
git diff --check
```

首个任务允许契约测试先以“章节未完成”形式验证失败，再在同一任务内创建三十二个符合结构的初始完整章节骨架；骨架必须包含本章具体目标、素材路径和验收任务，不能使用 `TODO`、`TBD` 或省略号。后续任务把骨架扩展为完整正文。

### 提交

```text
docs: scaffold data analyst agent course v2
```

## 4. Task 2：第一部分——阅读、运行和调试项目

### 章节文件

- `part01-foundations/chapter01-project-architecture.md`
- `part01-foundations/chapter02-python-async-and-models.md`
- `part01-foundations/chapter03-sql-duckdb-domain.md`
- `part01-foundations/chapter04-environment-config-debugging.md`

### 核心素材

- `README.md`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/models/schemas.py`
- `backend/app/agents/graph.py`
- `frontend/src/main.js`
- `database/init.sql`
- `database/seed_data.py`
- `docs/database_design_md.md`
- `backend/tests/test_health.py`
- `backend/tests/test_seed_data.py`

### 必须讲清

- Data Analyst、NL2SQL 和受控 Agent 的差别。
- Python 包、模块、类型标注、Pydantic、`async`/`await` 和依赖注入在项目中的用途。
- 八张表、主外键、JOIN、聚合、时间维度和 DuckDB/PostgreSQL 边界。
- `.env`、Settings、日志、异常堆栈、断点和最小测试定位方法。
- 第一次只读导航：从 `/api/chat/query` 找到 AgentGraph，再找到数据库执行和响应模型。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_health.py backend/tests/test_seed_data.py -q
git diff --check
```

### 提交

```text
docs: add course v2 foundations
```

## 5. Task 3：第二部分——最小 NL2SQL 闭环

### 章节文件

- `part02-minimum-nl2sql/chapter05-database-schema-loader.md`
- `part02-minimum-nl2sql/chapter06-fastapi-boundaries.md`
- `part02-minimum-nl2sql/chapter07-openai-compatible-llm.md`
- `part02-minimum-nl2sql/chapter08-minimum-nl2sql-pipeline.md`

### 核心素材

- `backend/app/db/connection.py`
- `backend/app/db/schema_loader.py`
- `backend/app/db/query_runner.py`
- `backend/app/api/query.py`
- `backend/app/api/schema.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/prompt_registry.py`
- `backend/app/agents/sql_generator.py`
- `backend/app/agents/answer_generator.py`
- 对应测试文件

### 必须讲清

- 数据库连接、Schema 读取、格式化和隔离测试库。
- FastAPI 路由、请求模型、响应模型、依赖和统一异常。
- OpenAI-compatible 消息格式、结构化 JSON、超时、重试、空 content 和 Secret 边界。
- 最小问题到 SQL、执行结果和答案的完整数据流。
- 为什么最小闭环不能直接用于真实数据库：缺少危险意图、AST Guard 和权限。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_schema_loader.py backend/tests/test_query_runner.py backend/tests/test_llm_service.py backend/tests/test_sql_generator.py backend/tests/test_query_api.py -q
git diff --check
```

### 提交

```text
docs: teach the minimum nl2sql pipeline
```

## 6. Task 4：第三部分——结构化意图与 Agent 工作流

### 章节文件

- `part03-agent/chapter09-analysis-intent.md`
- `part03-agent/chapter10-semantic-and-metadata.md`
- `part03-agent/chapter11-grounding-and-clarification.md`
- `part03-agent/chapter12-langgraph-state-and-routing.md`
- `part03-agent/chapter13-repair-optimizer-multiturn.md`

### 核心素材

- `backend/app/analysis_intent/`
- `backend/app/semantic/`
- `backend/app/schema_context/`
- `backend/app/agents/grounding.py`
- `backend/app/agents/clarification.py`
- `backend/app/agents/state.py`
- `backend/app/agents/graph.py`
- `backend/app/agents/progress_notifier.py`
- `backend/app/agents/sql_repair.py`
- `backend/app/agents/sql_optimizer.py`
- `backend/app/agents/session_store.py`
- 对应测试与评测 cases

### 必须讲清

- 规则与 LLM 意图候选如何合并，指标、维度、筛选和缺失槽位如何表达。
- 业务词、语义指标、元数据候选、物理字段和 JOIN 路由的关系。
- 澄清为什么必须发生在 SQL 生成和数据库访问之前。
- 十二个 LangGraph 节点、主要 state 字段、条件边、终止点和 Repair 回流。
- 进度通知为什么从图编排中拆出；失败和越权轮次为什么不能进入多轮上下文。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_analysis_intent_integration.py backend/tests/test_semantic_loader.py backend/tests/test_metadata_catalog.py backend/tests/test_agent_graph.py backend/tests/test_progress_notifier.py backend/tests/test_sql_repair.py backend/tests/test_session_store.py -q
git diff --check
```

### 提交

```text
docs: teach the complete agent workflow
```

## 7. Task 5：第四部分——安全、权限与可靠性

### 章节文件

- `part04-safety/chapter14-intent-and-sql-guards.md`
- `part04-safety/chapter15-sandbox-limit-timeout.md`
- `part04-safety/chapter16-auth-permission-row-filter.md`
- `part04-safety/chapter17-retry-failure-isolation.md`
- `part04-safety/chapter18-audit-and-observability.md`

### 核心素材

- `backend/app/security/intent_guard.py`
- `backend/app/security/sql_guard.py`
- `backend/app/db/sandbox.py`
- `backend/app/security/auth.py`
- `backend/app/security/permission_policy.py`
- `backend/app/security/data_permission.py`
- `backend/app/security/data_permissions.yaml`
- `backend/app/services/llm_service.py`
- `backend/app/utils/exceptions.py`
- `backend/app/agents/audit.py`
- `backend/app/services/llm_observability.py`
- 2026-07-15 至 2026-07-17 的权限、答案隔离和真实模型证据提交

### 必须讲清

- 自然语言危险意图与生成 SQL 危险结构的两层边界。
- SQLGlot AST、SELECT/WITH 白名单、系统对象、危险函数和 LIMIT。
- JWT/API Key、角色、表列权限、query scope 和 analyst 行级 SQL 改写。
- 网络重试、SQL Repair 重试和用户重试不是同一概念。
- SQL 已成功但答案生成失败时，为什么要保留结构化查询结果并隔离失败。
- 审计记录哪些证据、为什么不能保存原始凭据和完整供应商响应。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_intent_guard.py backend/tests/test_sql_guard.py backend/tests/test_auth.py backend/tests/test_data_permission_guard.py backend/tests/test_llm_service.py backend/tests/test_audit_report.py backend/tests/test_llm_observability.py -q
git diff --check
```

### 提交

```text
docs: teach agent safety permission and reliability
```

## 8. Task 6：第五部分——API、前端与部署产品化

### 章节文件

- `part05-product/chapter19-query-sse-cache.md`
- `part05-product/chapter20-vue-pinia-workbench.md`
- `part05-product/chapter21-chart-export-audit-ui.md`
- `part05-product/chapter22-docker-nginx-readiness.md`

### 核心素材

- `backend/app/api/query.py`
- `backend/app/services/query_cache.py`
- `backend/app/services/tracing.py`
- `frontend/src/views/Home.vue`
- `frontend/src/stores/query.js`
- `frontend/src/api/agent.js`
- `frontend/src/components/`
- `frontend/src/utils/spreadsheet.js`
- `frontend/tests/` 与 `frontend/e2e/`
- Dockerfile、Nginx、Compose、Alembic 和 readiness 代码

### 必须讲清

- 同步 Query API 与 SSE 进度的契约、取消、断连和缓存边界。
- Vue 组件、Pinia 状态、Axios 请求、图表和审计面板的数据流。
- SpreadsheetML 导出为什么要处理公式注入。
- DuckDB 固定重建与 PostgreSQL Alembic 的生命周期差异。
- demo profile 与 secure profile 的配置边界，以及 readiness fail closed。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_query_api.py backend/tests/test_query_cache.py backend/tests/test_migrations.py backend/tests/test_deployment_profiles.py -q
npm run test --prefix frontend
npm run build --prefix frontend
git diff --check
```

### 提交

```text
docs: teach the agent product surface
```

## 9. Task 7：第六部分上——测试和专项评测

### 章节文件

- `part06-quality/chapter23-test-pyramid.md`
- `part06-quality/chapter24-nl2sql-intent-permission-evaluation.md`
- `part06-quality/chapter25-repair-and-result-correctness.md`

### 核心素材

- `backend/tests/`
- `frontend/tests/`
- `frontend/e2e/`
- `backend/evaluation/evaluator.py`
- `backend/evaluation/intent_grounding_evaluator.py`
- `backend/evaluation/permission_evaluator.py`
- `backend/evaluation/repair_evaluator.py`
- `backend/evaluation/result_correctness_evaluator.py`
- `backend/evaluation/cases/`
- 历史真实 Qwen 基线报告

### 必须讲清

- 单元、集成、E2E、核心路径、专项评测和真实模型评测的证据边界。
- 安全阻断不能计作普通执行失败。
- SQL 可执行不等于结果正确，黄金 SQL、比较器、排序和浮点容差的作用。
- 固定故障注入如何单独证明 SQL Repair。
- 指标分母、样本数量、provider、model 和 HEAD 必须一起解释。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_evaluator.py backend/tests/test_intent_grounding_evaluator.py backend/tests/test_permission_evaluator.py backend/tests/test_repair_evaluator.py backend/tests/test_result_correctness_evaluator.py -q
git diff --check
```

### 提交

```text
docs: teach testing and evaluation evidence
```

## 10. Task 8：第六部分下——真实模型证据和事故复盘

### 章节文件

- `part06-quality/chapter26-sharding-checkpoint-aggregation.md`
- `part06-quality/chapter27-github-actions-quality-gate.md`
- `part06-quality/chapter28-mimo-timeout-incident.md`

### 核心素材

- `backend/evaluation/shard_support.py`
- `backend/evaluation/shard_report_aggregator.py`
- 三类 evaluator 的分片 CLI
- `.github/workflows/real-qwen-evaluation.yml`
- `backend/evaluation/quality_gate.py`
- `backend/evaluation/security_audit_exporter.py`
- `docs/superpowers/specs/2026-07-18-v1.7-real-llm-evaluation-sharding-design.md`
- GitHub Actions run `29634864907` 的脱敏结果

### 必须讲清

- round-robin 固定分片、每 case 原子 checkpoint、分片元数据和 artifact。
- 严格汇总如何拒绝缺片、重复 case、错误 SHA、错误模型和错误 case 哈希。
- 普通 CI 为什么不能注入真实模型 Secret，真实工作流为什么需要手动授权。
- run `29634864907`：Preflight 成功；NL2SQL 8/13 成功、5/13 在 75 分钟超时；Repair 3/3、Correctness 5/5 成功；最终门禁因 NL2SQL 不完整失败。
- MiMo 多次返回 reasoning 但 content 为空，重试放大尾延迟；这不是 API Key 缺失或 SQL Repair 全面失败。
- 当前证据能证明什么、不能证明什么，以及下一版单 case deadline、快速失败和续跑方向。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_shard_support.py backend/tests/test_shard_report_aggregator.py backend/tests/test_workflow_files.py backend/tests/test_quality_gate.py backend/tests/test_security_audit_exporter.py -q
git diff --check
```

不得在本任务中触发、重跑或取消任何 GitHub Actions，也不得调用真实 MiMo。

### 提交

```text
docs: teach resilient real model evidence
```

## 11. Task 9：第七部分——独立开发与面试毕业

### 章节文件

- `part07-mastery/chapter29-add-business-metric.md`
- `part07-mastery/chapter30-debugging-lab.md`
- `part07-mastery/chapter31-rebuild-mini-agent.md`
- `part07-mastery/chapter32-interview-defense.md`

### 内容要求

#### 第29章：增加业务指标

以一个不与现有答案完全重复的新指标为练习，要求学习者完成语义定义、别名、Grounding、SQL、权限、黄金结果、测试、评测和可选前端展示。正文提供验收清单和分层提示，不直接给出完整补丁。

#### 第30章：综合调试实验

设计至少四个可恢复故障：工作目录错误、Schema/字段错误、权限误判和 LLM 空响应。学习者必须提交现象、最小复现、假设、证据、根因、修复和回归测试。

#### 第31章：重写精简版 Agent

在独立学习目录中定义约束：FastAPI 可选，必须包含 Schema 输入、结构化 LLM 接口、SELECT-only Guard、DuckDB 执行、结构化失败、Fake LLM 和确定性测试。提供接口契约和测试目标，不复制生产实现。

#### 第32章：面试答辩

包含 30 秒、5 分钟和 10 分钟三种介绍；Agent 编排、安全、权限、评测、CI、事故和项目边界追问；提供评分表而非需要背诵的唯一答案。

### 验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py -q
git diff --check
```

### 提交

```text
docs: add course v2 mastery and interview labs
```

## 12. Task 10：全课程审计和最终交付

### 规格符合性审查

- 独立目录、七部分、三十二章和八个总览文件完整。
- 每章十四项教学结构完整，内容与章名和设计目标一致。
- 旧课程没有被修改或引用。
- 当前核心模块在 Code Map 中都有负责章节。
- 第28章如实记录 run 结果，不把未完成 NL2SQL 报告包装为通过。
- 第29～31章存在真正的编码、调试和重建验收，而非纯阅读。

### 内容质量审查

- 解释适合 Python/SQL 初级学习者，但没有改变技术含义。
- 术语一致，事实、推测、历史结果和当前边界明确区分。
- 代码片段短小且配有解释，命令工作目录和外部条件明确。
- 无 Secret、无大段生产源码复制、无失效本地路径。
- Markdown 导航、围栏、标题、引用块和表格可读。

### 最终验证

```bash
pytest backend/tests/test_learning_course_v2_docs.py backend/tests/test_project_docs_consistency.py -q
pytest backend/tests/test_learning_course_docs.py -q
npm run test --prefix frontend
npm run build --prefix frontend
git diff --check
```

若完整后端回归时间允许，再运行：

```bash
pytest backend -q
```

### 最终提交

```text
docs: complete data analyst agent course v2
```

## 13. 任务完成报告

每个任务完成后报告：

- 新增或扩展的章节。
- 两阶段审查结论。
- 实际执行的验证与结果。
- 未执行的外部步骤及原因。
- 对应提交哈希。

最终交付只总结课程入口、章节数量、验证、提交和已知边界，不在对话中粘贴全部正文。
