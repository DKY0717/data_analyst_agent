# 当前代码与课程映射

> **首版源码基线：** `8dffc1d76c514c7efe1b6e642ea1880a81989109`
>
> 这份映射同时回答两个问题：学习某章应该看哪些代码；看到某个核心模块时应该回到哪一章学习。路径只指向当前仓库，不依赖旧课程。

## 1. 章节到当前代码

| 章节 | 主要源码或配置 | 主要验证证据 |
|---|---|---|
| 1 | `README.md`、`backend/app/main.py`、`backend/app/agents/graph.py` | `backend/tests/test_health.py` |
| 2 | `backend/app/models/schemas.py`、`backend/app/config.py` | `backend/tests/test_query_api.py` |
| 3 | `database/init.sql`、`database/seed_data.py` | `backend/tests/test_seed_data.py` |
| 4 | `.env.example`、`backend/app/utils/logger.py`、`backend/app/utils/exceptions.py` | `backend/tests/test_health.py` |
| 5 | `backend/app/db/connection.py`、`backend/app/db/schema_loader.py` | `backend/tests/test_schema_loader.py` |
| 6 | `backend/app/api/query.py`、`backend/app/models/schemas.py` | `backend/tests/test_query_api.py` |
| 7 | `backend/app/services/llm_service.py`、`backend/app/services/prompt_registry.py` | `backend/tests/test_llm_service.py` |
| 8 | `backend/app/agents/sql_generator.py`、`backend/app/db/query_runner.py`、`backend/app/agents/answer_generator.py` | `backend/tests/test_sql_generator.py`、`backend/tests/test_query_runner.py` |
| 9 | `backend/app/analysis_intent/` | `backend/tests/test_analysis_intent_integration.py` |
| 10 | `backend/app/semantic/`、`backend/app/schema_context/` | `backend/tests/test_semantic_loader.py`、`backend/tests/test_metadata_catalog.py` |
| 11 | `backend/app/agents/grounding.py`、`backend/app/agents/clarification.py` | `backend/tests/test_schema_grounding_precision.py` |
| 12 | `backend/app/agents/state.py`、`backend/app/agents/graph.py`、`backend/app/agents/progress_notifier.py` | `backend/tests/test_agent_graph.py`、`backend/tests/test_progress_notifier.py` |
| 13 | `backend/app/agents/sql_repair.py`、`backend/app/agents/sql_optimizer.py`、`backend/app/agents/session_store.py` | `backend/tests/test_sql_repair.py`、`backend/tests/test_session_store.py` |
| 14 | `backend/app/security/intent_guard.py`、`backend/app/security/sql_guard.py` | `backend/tests/test_intent_guard.py`、`backend/tests/test_sql_guard.py` |
| 15 | `backend/app/db/sandbox.py`、`backend/app/db/query_runner.py` | `backend/tests/test_query_runner.py` |
| 16 | `backend/app/security/auth.py`、`backend/app/security/data_permission.py`、`backend/app/security/data_permissions.yaml` | `backend/tests/test_auth.py`、`backend/tests/test_data_permission_guard.py` |
| 17 | `backend/app/services/llm_service.py`、`backend/app/utils/exceptions.py`、`backend/app/agents/graph.py` | `backend/tests/test_llm_service.py`、`backend/tests/test_agent_graph.py` |
| 18 | `backend/app/agents/audit.py`、`backend/app/services/llm_observability.py` | `backend/tests/test_audit_report.py`、`backend/tests/test_llm_observability.py` |
| 19 | `backend/app/api/query.py`、`backend/app/services/query_cache.py` | `backend/tests/test_query_api.py`、`backend/tests/test_query_cache.py` |
| 20 | `frontend/src/views/Home.vue`、`frontend/src/stores/query.js`、`frontend/src/api/agent.js` | `frontend/tests/` |
| 21 | `frontend/src/components/`、`frontend/src/utils/spreadsheet.js` | `frontend/e2e/` |
| 22 | `backend/Dockerfile`、`frontend/Dockerfile`、`frontend/nginx.conf`、`docker-compose.yml`、`backend/alembic/` | `backend/tests/test_deployment_profiles.py`、`backend/tests/test_migrations.py` |
| 23 | `backend/tests/`、`frontend/tests/`、`frontend/e2e/` | pytest、Vitest、Playwright |
| 24 | `backend/evaluation/evaluator.py`、`backend/evaluation/intent_grounding_evaluator.py`、`backend/evaluation/permission_evaluator.py` | `backend/evaluation/cases/` |
| 25 | `backend/evaluation/repair_evaluator.py`、`backend/evaluation/result_correctness_evaluator.py` | `backend/tests/test_repair_evaluator.py`、`backend/tests/test_result_correctness_evaluator.py` |
| 26 | `backend/evaluation/shard_support.py`、`backend/evaluation/shard_report_aggregator.py` | `backend/tests/test_shard_support.py`、`backend/tests/test_shard_report_aggregator.py` |
| 27 | `.github/workflows/ci.yml`、`.github/workflows/real-qwen-evaluation.yml`、`backend/evaluation/quality_gate.py` | `backend/tests/test_workflow_files.py`、`backend/tests/test_quality_gate.py` |
| 28 | `backend/app/services/llm_service.py`、`backend/evaluation/shard_support.py` | GitHub Actions run `29634864907` 的脱敏日志与 artifact |
| 29 | `backend/app/semantic/ecommerce_metrics.yaml`、`backend/evaluation/cases/` | 语义、Grounding、黄金结果和前端相关测试 |
| 30 | `backend/app/`、`backend/tests/` | 最小复现、根因、修复和回归测试 |
| 31 | `backend/app/services/llm_service.py`、`backend/app/security/sql_guard.py`、`backend/app/db/query_runner.py` | 独立学习实现的确定性测试 |
| 32 | `docs/interview_guide.md`、`docs/resume_project_packet.md` | 架构图、演示证据和模拟问答评分 |

## 2. 核心区域到负责章节

| 核心区域 | 负责章节 |
|---|---|
| `backend/app/agents/` | 8、11～13、17～18 |
| `backend/app/analysis_intent/` | 9 |
| `backend/app/db/` | 5、8、15 |
| `backend/app/security/` | 14、16 |
| `backend/app/semantic/` | 10、29 |
| `backend/app/schema_context/` | 10～11 |
| `backend/app/services/` | 7、17～19 |
| `backend/app/api/` | 6、19 |
| `backend/evaluation/` | 24～28 |
| `backend/tests/` | 23～30 |
| `frontend/src/` | 20～21 |
| `frontend/tests/`、`frontend/e2e/` | 21、23 |
| `database/`、`backend/alembic/` | 3、5、22 |
| `.github/workflows/` | 27～28 |

## 3. 使用方法

> 阅读章节前先从第一张表找到入口文件和最小验证；修改代码前再从第二张表检查该模块是否还影响其他章节。项目更新时应同时更新两个方向，避免课程只覆盖主流程却遗漏测试、评测或交付配置。
