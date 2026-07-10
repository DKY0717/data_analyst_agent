# 代码与章节映射

> 这张表把每章知识点映射到当前项目的核心源码、测试和最小验收命令。阅读章节前可以先知道要观察哪些文件；项目重构后也可以用它快速判断哪些文档需要同步修改。

> 表格中的命令默认在项目根目录执行。涉及真实 LLM 的行为会在正文中单独说明环境变量和费用条件。

| 章节 | 核心源码或配置 | 主要验证证据 | 最小验收命令 |
|---|---|---|---|
| 第1章 项目概览 | `README.md`、`backend/app/main.py`、`backend/app/agents/graph.py` | `backend/tests/test_health.py` | `pytest backend/tests/test_health.py -q` |
| 第2章 环境与 Python | `.env.example`、`backend/requirements.txt`、`frontend/package.json`、`backend/app/config.py` | `backend/tests/test_health.py` | `pytest backend/tests/test_health.py -q` |
| 第3章 数据库与业务模型 | `database/init.sql`、`database/seed_data.py`、`docs/database_design_md.md` | `backend/tests/test_seed_data.py` | `pytest backend/tests/test_seed_data.py -q` |
| 第4章 Schema 加载 | `backend/app/db/connection.py`、`backend/app/db/schema_loader.py`、`backend/app/utils/schema_formatter.py` | `backend/tests/test_schema_loader.py` | `pytest backend/tests/test_schema_loader.py -q` |
| 第5章 FastAPI | `backend/app/main.py`、`backend/app/api/health.py`、`backend/app/api/schema.py`、`backend/app/models/schemas.py` | `backend/tests/test_health.py`、`backend/tests/test_query_api.py` | `pytest backend/tests/test_health.py backend/tests/test_query_api.py -q` |
| 第6章 LLM 服务 | `backend/app/services/llm_service.py`、`backend/app/services/prompt_registry.py` | `backend/tests/test_llm_service.py` | `pytest backend/tests/test_llm_service.py -q` |
| 第7章 NL2SQL 最小链路 | `backend/app/agents/sql_generator.py`、`backend/app/db/query_runner.py`、`backend/app/agents/answer_generator.py` | `backend/tests/test_sql_generator.py`、`backend/tests/test_query_runner.py` | `pytest backend/tests/test_sql_generator.py backend/tests/test_query_runner.py -q` |
| 第8章 SQL 安全 | `backend/app/security/intent_guard.py`、`backend/app/security/sql_guard.py`、`backend/app/db/sandbox.py` | `backend/tests/test_intent_guard.py`、`backend/tests/test_sql_guard.py` | `pytest backend/tests/test_intent_guard.py backend/tests/test_sql_guard.py -q` |
| 第9章 分析意图 | `backend/app/analysis_intent/` | `backend/tests/test_analysis_intent_integration.py` | `pytest backend/tests/test_analysis_intent_integration.py -q` |
| 第10章 语义与 Grounding | `backend/app/semantic/`、`backend/app/schema_context/`、`backend/app/agents/grounding.py`、`backend/app/agents/clarification.py` | `backend/tests/test_semantic_loader.py`、`backend/tests/test_metadata_catalog.py` | `pytest backend/tests/test_semantic_loader.py backend/tests/test_metadata_catalog.py -q` |
| 第11章 LangGraph | `backend/app/agents/state.py`、`backend/app/agents/graph.py` | `backend/tests/test_agent_graph.py` | `pytest backend/tests/test_agent_graph.py -q` |
| 第12章 修复与多轮 | `backend/app/agents/sql_repair.py`、`backend/app/agents/sql_optimizer.py`、`backend/app/agents/session_store.py` | `backend/tests/test_sql_repair.py`、`backend/tests/test_session_store.py` | `pytest backend/tests/test_sql_repair.py backend/tests/test_session_store.py -q` |
| 第13章 认证与权限 | `backend/app/security/auth.py`、`backend/app/security/data_permission.py`、`backend/app/security/data_permissions.yaml`、`backend/app/agents/audit.py` | `backend/tests/test_auth.py`、`backend/tests/test_data_permission_guard.py` | `pytest backend/tests/test_auth.py backend/tests/test_data_permission_guard.py -q` |
| 第14章 SSE 与可观测性 | `backend/app/api/query.py`、`backend/app/services/query_cache.py`、`backend/app/services/tracing.py`、`backend/app/services/llm_observability.py` | `backend/tests/test_query_cache.py`、`backend/tests/test_llm_observability.py` | `pytest backend/tests/test_query_cache.py backend/tests/test_llm_observability.py -q` |
| 第15章 Vue 工作台 | `frontend/src/views/Home.vue`、`frontend/src/stores/query.js`、`frontend/src/components/` | `frontend/tests/` | `npm run test --prefix frontend` |
| 第16章 自动化测试 | `backend/tests/`、`frontend/tests/`、`frontend/e2e/` | pytest、Vitest、Playwright 测试套件 | `pytest backend/tests/test_core_path_cases.py -q` |
| 第17章 评测体系 | `backend/evaluation/`、`backend/evaluation/cases/`、`backend/evaluation/quality_gate.py` | `backend/tests/test_evaluator.py`、`backend/tests/test_quality_gate.py` | `pytest backend/tests/test_evaluator.py backend/tests/test_quality_gate.py -q` |
| 第18章 Docker 与 CI | `backend/Dockerfile`、`frontend/Dockerfile`、`frontend/nginx.conf`、`docker-compose.yml`、`.github/workflows/` | `backend/tests/test_workflow_files.py` | `pytest backend/tests/test_workflow_files.py -q` |
| 第19章 完整复现 | `README.md`、`scripts/interview_demo_preflight.py`、`backend/evaluation/cases/core_path_cases.yaml` | `backend/tests/test_interview_demo_preflight_script.py`、`backend/tests/test_core_path_cases.py` | `pytest backend/tests/test_interview_demo_preflight_script.py backend/tests/test_core_path_cases.py -q` |

## 如何使用映射表

> 如果一章涉及多个模块，先从表格中的第一个源码文件开始，找到对外入口，再沿函数调用进入下游。测试文件通常比实现文件更容易展示输入和预期输出，适合在阅读实现前建立行为预期。
>
> 当源码路径存在但测试命令失败时，不要立刻修改代码。先确认 Python 环境、依赖、工作目录和测试数据库是否正确，再根据错误信息判断是环境问题、文档漂移还是代码回归。

