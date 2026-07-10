# Data Analyst Agent 零基础学习教程实施计划

> 对应设计：`docs/superpowers/specs/2026-07-10-data-analyst-agent-learning-course-design.md`
>
> 教学基线：`4d71b3ce84cffe175fffaffa252a9072d6e79d18`

## 1. 实施原则

- 全部正文使用中文，目录和文件名使用稳定的英文小写短横线形式。
- 课程采用五部分十九章，每章一个 Markdown 文件，章内按编号分节。
- 当前仓库源码是实现事实来源，不复制十九份完整项目。
- 每章必须包含目标、问题场景、概念、代码地图、关键实现、流程、验证、错误、小结、练习和下一章衔接。
- 解释文字使用 Markdown 引用块；代码、命令、SQL、JSON、YAML 和日志使用带语言标识的代码块。
- 每章至少提供一个可执行或可观察的验收步骤。
- 不创建空章节，不使用待办标记、省略符或概括性短句替代应当完整编写的正文。
- 每个批次完成后先做规格符合性复核，再做内容质量复核，验证通过后独立提交。
- 工作树中已有的非教程改动属于用户或其他任务，不修改、不暂存、不提交。

## 2. Task 1：课程站点骨架

### 新建文件

- `user_docs/data-analyst-agent-course/README.md`
- `user_docs/data-analyst-agent-course/_sidebar.md`
- `user_docs/data-analyst-agent-course/index.html`
- `user_docs/data-analyst-agent-course/CHANGELOG.md`
- `user_docs/data-analyst-agent-course/CODE-MAP.md`
- `backend/tests/test_learning_course_docs.py`

### 内容要求

- 首页说明课程定位、读者、教学基线、学习收获、五部分十九章导航、环境成本提示和维护策略。
- 侧边栏完整列出十九章，链接与实际文件保持一致。
- Docsify 页面支持侧边栏、搜索、代码复制、分页导航、语法高亮和 Mermaid。
- Changelog 记录第一版基线与后续更新规则。
- Code Map 建立十九章到核心源码、测试和验收命令的映射。
- 文档契约测试检查文件存在、章节数量、侧边栏链接、代码路径、占位符、代码围栏和必要章节结构。

### 验证

```bash
pytest backend/tests/test_learning_course_docs.py -q
git diff --check
```

### 提交

```text
docs: scaffold data analyst agent learning course
```

## 3. Task 2：第一部分——基础准备

### 新建文件

- `part01-foundations/chapter01-project-overview.md`
- `part01-foundations/chapter02-development-environment-and-python.md`
- `part01-foundations/chapter03-database-sql-and-domain-model.md`

### 第一章：认识 Data Analyst Agent

核心素材：

- `README.md`
- `backend/app/main.py`
- `backend/app/agents/graph.py`
- `frontend/src/App.vue`
- `user_docs/knowledge_notes/01-项目概览与环境搭建.md`

必须讲清：项目问题、输入输出、完整链路、技术栈、目录、确定性代码和 LLM 的边界、学习方法、第一次只读运行检查。

### 第二章：开发环境与必备 Python 基础

核心素材：

- `.env.example`
- `backend/requirements.txt`
- `frontend/package.json`
- `backend/app/config.py`
- `user_docs/dev_guide/00-开始之前你需要知道的基础知识.md`
- `user_docs/dev_guide/01-准备工作与第一个可运行程序.md`

必须讲清：Python 模块、虚拟环境、依赖、类型标注、Pydantic、同步与异步、环境变量、Node.js/npm、启动命令和常见环境错误。

### 第三章：数据库、SQL 与电商业务模型

核心素材：

- `database/init.sql`
- `database/init_pg.sql`
- `database/seed_data.py`
- `docs/database_design_md.md`
- `skills/ecommerce-schema/SKILL.md`

必须讲清：关系型数据库、主外键、八张业务表、JOIN、聚合、时间维度、DuckDB/PostgreSQL 差异和代表性安全查询。

### 验证

```bash
pytest backend/tests/test_learning_course_docs.py -q
pytest backend/tests/test_seed_data.py -q
git diff --check
```

### 提交

```text
docs: add course foundations chapters
```

## 4. Task 3：第二部分——构建最小可用系统

### 新建文件

- `part02-minimum-system/chapter04-database-init-and-schema.md`
- `part02-minimum-system/chapter05-fastapi-backend.md`
- `part02-minimum-system/chapter06-openai-compatible-llm.md`
- `part02-minimum-system/chapter07-first-nl2sql-pipeline.md`

### 第四章：初始化数据库与加载 Schema

核心素材：

- `backend/app/db/connection.py`
- `backend/app/db/schema_loader.py`
- `backend/app/utils/schema_formatter.py`
- `backend/app/db/demo_bootstrap.py`
- `backend/tests/test_schema_loader.py`

必须讲清：连接生命周期、information_schema、SchemaContext、格式化、演示数据库自举和隔离测试库。

### 第五章：搭建 FastAPI 后端

核心素材：

- `backend/app/main.py`
- `backend/app/api/health.py`
- `backend/app/api/schema.py`
- `backend/app/models/schemas.py`
- `backend/app/utils/exceptions.py`

必须讲清：应用实例、lifespan、路由、依赖注入、Pydantic 契约、CORS、错误边界、存活与就绪检查。

### 第六章：接入 OpenAI-compatible 大模型

核心素材：

- `backend/app/services/llm_service.py`
- `backend/app/services/prompt_registry.py`
- `backend/app/services/llm_observability.py`
- `backend/tests/test_llm_service.py`
- `skills/qwen-api-patterns/SKILL.md`

必须讲清：兼容接口、模型配置、消息结构、结构化输出、重试、超时、错误分类、Secret 安全和 Mock 测试。

### 第七章：完成第一条自然语言转 SQL 链路

核心素材：

- `backend/app/agents/sql_generator.py`
- `backend/app/db/query_runner.py`
- `backend/app/agents/answer_generator.py`
- `backend/app/api/query.py`
- `backend/tests/test_sql_generator.py`
- `backend/tests/test_query_api.py`

必须讲清：问题、Schema、Prompt、SQL、执行结果、自然语言答案和 API 响应如何连接成最小闭环，同时明确尚未加入安全与修复时的风险。

### 验证

```bash
pytest backend/tests/test_learning_course_docs.py -q
pytest backend/tests/test_schema_loader.py backend/tests/test_health.py backend/tests/test_llm_service.py backend/tests/test_sql_generator.py backend/tests/test_query_api.py -q
git diff --check
```

### 提交

```text
docs: add minimum nl2sql system chapters
```

## 5. Task 4：第三部分上——安全、意图与 Grounding

### 新建文件

- `part03-agent-workflow/chapter08-sql-safety.md`
- `part03-agent-workflow/chapter09-analysis-intent.md`
- `part03-agent-workflow/chapter10-semantic-grounding-clarification.md`

### 第八章：构建 SQL 安全防护

核心素材：

- `backend/app/security/intent_guard.py`
- `backend/app/security/sql_guard.py`
- `backend/app/db/sandbox.py`
- `backend/app/security/error_classifier.py`
- `backend/tests/test_intent_guard.py`
- `backend/tests/test_sql_guard.py`
- `skills/sql-safety-rules/SKILL.md`

必须讲清：Intent Guard 和 SQL Guard 的职责边界、SQLGlot AST、SELECT/WITH 限制、LIMIT、危险函数、系统表、文件访问、沙箱和 fail-closed。

### 第九章：解析结构化分析意图

核心素材：

- `backend/app/analysis_intent/models.py`
- `backend/app/analysis_intent/rule_parser.py`
- `backend/app/analysis_intent/llm_parser.py`
- `backend/app/analysis_intent/merger.py`
- `backend/tests/test_analysis_intent_integration.py`

必须讲清：指标、维度、过滤、排序、排名、缺失槽位、规则与 LLM 双路解析、置信度、冲突与合并。

### 第十章：语义层、Schema Grounding 与主动澄清

核心素材：

- `backend/app/semantic/ecommerce_metrics.yaml`
- `backend/app/semantic/semantic_loader.py`
- `backend/app/schema_context/metadata_catalog.py`
- `backend/app/agents/grounding.py`
- `backend/app/agents/clarification.py`
- `backend/tests/test_semantic_loader.py`
- `backend/tests/test_metadata_catalog.py`

必须讲清：业务指标口径、别名、物理字段、JOIN 路径、元数据目录、Grounding 结果、低置信度和澄清候选。

### 验证

```bash
pytest backend/tests/test_learning_course_docs.py -q
pytest backend/tests/test_intent_guard.py backend/tests/test_sql_guard.py backend/tests/test_analysis_intent_integration.py backend/tests/test_semantic_loader.py backend/tests/test_metadata_catalog.py -q
git diff --check
```

### 提交

```text
docs: add safety intent and grounding chapters
```

## 6. Task 5：第三部分下——LangGraph、修复与多轮

### 新建文件

- `part03-agent-workflow/chapter11-langgraph-workflow.md`
- `part03-agent-workflow/chapter12-repair-optimization-multiturn.md`

### 第十一章：使用 LangGraph 编排工作流

核心素材：

- `backend/app/agents/state.py`
- `backend/app/agents/graph.py`
- `backend/tests/test_agent_graph.py`
- `skills/agent-workflow-constraints/SKILL.md`

必须讲清：StateGraph、共享状态、节点、普通边、条件边、状态更新、Guard 与权限拒绝终止、Repair 回流和完整运行入口。

### 第十二章：SQL 自动修复、优化与多轮分析

核心素材：

- `backend/app/agents/sql_repair.py`
- `backend/app/agents/sql_optimizer.py`
- `backend/app/agents/conversation_context.py`
- `backend/app/agents/session_store.py`
- `backend/tests/test_sql_repair.py`
- `backend/tests/test_conversation_context.py`

必须讲清：错误上下文、最多重试次数、修复后重新过 Guard、EXPLAIN 优化、多轮摘要、会话隔离、失败和越权轮次不得污染上下文。

### 验证

```bash
pytest backend/tests/test_learning_course_docs.py -q
pytest backend/tests/test_agent_graph.py backend/tests/test_sql_repair.py backend/tests/test_sql_optimizer.py backend/tests/test_conversation_context.py backend/tests/test_session_store.py -q
git diff --check
```

### 提交

```text
docs: add langgraph repair and conversation chapters
```

## 7. Task 6：第四部分——产品化

### 新建文件

- `part04-productization/chapter13-auth-permission-audit.md`
- `part04-productization/chapter14-sse-cache-observability.md`
- `part04-productization/chapter15-vue-workbench.md`

### 第十三章：身份认证、数据权限与安全审计

核心素材：

- `backend/app/security/auth.py`
- `backend/app/security/permission_policy.py`
- `backend/app/security/data_permission.py`
- `backend/app/security/data_permissions.yaml`
- `backend/app/agents/audit.py`
- `frontend/src/components/AuthBar.vue`
- `frontend/src/components/AuditPanel.vue`

必须讲清：JWT、API Key、角色、策略文件、表列权限、行级过滤、审计事件、认证关闭时的本地边界和演示角色。

### 第十四章：SSE、缓存、可观测性与成本统计

核心素材：

- `backend/app/api/query.py`
- `backend/app/services/query_cache.py`
- `backend/app/services/tracing.py`
- `backend/app/services/llm_observability.py`
- `backend/app/services/ab_test.py`
- `frontend/src/stores/query.js`

必须讲清：SSE 事件、进度回调、缓存键和失效、调用链、Token/耗时/成本、A/B 实验及不记录敏感 Prompt 的边界。

### 第十五章：开发 Vue 数据分析工作台

核心素材：

- `frontend/src/main.js`
- `frontend/src/App.vue`
- `frontend/src/views/Home.vue`
- `frontend/src/api/agent.js`
- `frontend/src/stores/query.js`
- `frontend/src/components/`
- `frontend/tests/`

必须讲清：Vue 组件、Props/Events、Pinia、Router、Axios、查询状态、SSE、表格、ECharts、Markdown、导出、响应式布局和权限演示。

### 验证

```bash
pytest backend/tests/test_learning_course_docs.py -q
pytest backend/tests/test_auth.py backend/tests/test_data_permission_guard.py backend/tests/test_query_cache.py backend/tests/test_tracing.py backend/tests/test_llm_observability.py -q
npm run test --prefix frontend
npm run build --prefix frontend
git diff --check
```

### 提交

```text
docs: add productization and vue workbench chapters
```

## 8. Task 7：第五部分——质量、部署与毕业设计

### 新建文件

- `part05-quality-and-graduation/chapter16-automated-testing.md`
- `part05-quality-and-graduation/chapter17-evaluation-and-quality-gate.md`
- `part05-quality-and-graduation/chapter18-docker-nginx-ci.md`
- `part05-quality-and-graduation/chapter19-reproduction-and-roadmap.md`

### 第十六章：后端、前端与端到端测试

核心素材：

- `backend/tests/conftest.py`
- `backend/tests/test_core_path_cases.py`
- `frontend/vitest.config.js`
- `frontend/playwright.config.js`
- `frontend/e2e/`
- `.github/workflows/ci.yml`

必须讲清：测试金字塔、隔离数据库、Mock 边界、pytest、Vitest、Playwright、确定性核心路径和测试数不等于测试质量。

### 第十七章：NL2SQL 评测体系与质量门禁

核心素材：

- `backend/evaluation/`
- `backend/evaluation/cases/`
- `backend/evaluation/quality_gate.py`
- `backend/run_spider_eval.py`
- `docs/Qwen_Plus_32条评测基线分析.md`

必须讲清：用例结构、生成成功、Guard、执行、正确性、修复、安全、Grounding、权限、报告、真实模型与确定性评测边界。

### 第十八章：Docker、Nginx 与持续集成

核心素材：

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/real-qwen-evaluation.yml`
- `scripts/check_secrets.py`

必须讲清：镜像、容器、卷、健康检查、反向代理、前后端网络、Secret Scan、普通 CI 与真实模型工作流分离。

### 第十九章：完整复现、项目复盘与继续优化

核心素材：

- `README.md`
- `scripts/interview_demo_preflight.py`
- `scripts/interview_evidence.py`
- `backend/evaluation/cases/core_path_cases.yaml`
- `docs/提升规划.md`

必须讲清：干净环境复现、本地与 Docker 两条路线、核心问题验收、安全演示、证据包、当前能力边界、后续优化与独立毕业任务。

### 验证

```bash
pytest backend/tests/test_learning_course_docs.py -q
pytest backend/tests/test_core_path_cases.py backend/tests/test_evaluator.py backend/tests/test_quality_gate.py backend/tests/test_workflow_files.py -q
git ls-files -z | python scripts/check_secrets.py
git diff --check
```

### 提交

```text
docs: add testing evaluation deployment and graduation chapters
```

## 9. Task 8：全课程完成审计

### 审计范围

1. 十九章文件全部存在且非空。
2. README、侧边栏、Code Map 的章节链接完全一致。
3. 所有引用的本地源码、测试、配置和脚本路径存在。
4. 每章具备完整必需结构和至少一个验收命令。
5. 不存在待办标记、空章节和省略式占位内容。
6. 所有 Markdown 代码围栏闭合。
7. Docsify 首页、侧边栏和至少十九章链接可通过本地 HTTP 访问。
8. 课程契约测试通过。
9. 后端文档一致性相关测试通过。
10. 前端单测和生产构建通过。
11. Secret Scan 不泄露本地凭据。
12. 两阶段人工复核通过。

### 最终验证

```bash
pytest backend/tests/test_learning_course_docs.py backend/tests/test_project_docs_consistency.py -q
npm run test --prefix frontend
npm run build --prefix frontend
git diff --check
```

### 最终提交

```text
docs: complete data analyst agent learning course
```

## 10. 工作日记与交付

每个批次完成后更新 `logs/work-diary.md`，记录：

- 完成的章节；
- 对应提交；
- 实际验证结果；
- 未运行的外部依赖步骤；
- 下一个批次。

最终交付回复只总结课程位置、章节数、验证结果、提交和已知外部条件，不在对话中重复粘贴十九章正文。
