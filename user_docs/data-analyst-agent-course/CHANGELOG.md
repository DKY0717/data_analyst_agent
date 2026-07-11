# 课程更新日志

> 本文件记录课程结构、教学基线、源码路径和行为说明的变化。项目功能升级后，应当先判断影响章节，再修改正文和映射表。

## 2026-07-10

### 完成第一部分：基础准备

> 已完成第 1～3 章，覆盖项目完整链路、开发环境、必备 Python 概念、八张电商表、SQL 基础和可重复种子数据。首页和侧边栏已加入可访问章节链接，课程进度更新为 3/19。

| 章节 | 主要验证 |
|---|---|
| 第1章 | FastAPI 入口导入、后端健康检查测试 |
| 第2章 | Settings 导入、前端生产构建 |
| 第3章 | 隔离 DuckDB 种子数据重复运行测试 |

### 建立第一版课程基线

> 第一版课程固定对应项目提交 `4d71b3ce84cffe175fffaffa252a9072d6e79d18`，采用五部分十九章结构。
>
> 当前已建立课程首页、阅读站入口、侧边栏、代码映射和文档契约测试。章节会按基础准备、最小系统、Agent 工作流、产品化、质量与毕业设计的顺序完成。

| 项目 | 内容 |
|---|---|
| 教学基线 | `4d71b3ce84cffe175fffaffa252a9072d6e79d18` |
| 课程结构 | 5 部分、19 章 |
| 正文语言 | 中文 |
| 源码策略 | 当前仓库是实现事实来源，不复制完整源码快照 |
| 验证策略 | 每章至少一个可执行或可观察检查点 |

### 后续版本如何更新

> 项目代码发生变化时，按照以下顺序维护课程：
>
> 1. 识别接口、流程、路径或行为发生变化的模块；
> 2. 在 `CODE-MAP.md` 中定位受影响章节；
> 3. 使用当前代码和测试重新核对章节描述；
> 4. 运行章节验收命令；
> 5. 在本日志记录修改原因、范围和验证证据。

## 2026-07-11

### 完成第二部分：构建最小可用系统

> 已完成第 4～7 章，覆盖数据库连接与 Schema 加载、FastAPI 请求边界、OpenAI-compatible LLM 客户端，以及第一条自然语言转 SQL 闭环。四章都绑定当前源码、测试和验收命令，并明确最小链路尚未包含完整安全治理的边界。

| 章节 | 主要验证 |
|---|---|
| 第4章 | `backend/tests/test_schema_loader.py`、`/api/schema` |
| 第5章 | `backend/tests/test_health.py`、FastAPI `/docs` |
| 第6章 | `backend/tests/test_llm_service.py`、Mock 响应与异常 |
| 第7章 | `backend/tests/test_sql_generator.py`、`backend/tests/test_query_runner.py` |

> 课程进度更新为 7/19。真实 LLM 的端到端调用仍受 API Key、端点连通性和费用影响，正文只把确定性测试作为无费用验收证据。

### 完成第三部分上半段：安全、意图与 Grounding

> 已完成第 8～10 章，覆盖 Intent Guard、SQLGlot AST 安全校验、LIMIT 与沙箱、结构化分析意图、规则/LLM 双路解析、语义配置、元数据目录、JOIN 路由和主动澄清。正文明确区分了模型输出、业务概念和物理 SQL 的边界。

| 章节 | 主要验证 |
|---|---|
| 第8章 | `backend/tests/test_intent_guard.py`、`backend/tests/test_sql_guard.py` |
| 第9章 | `backend/tests/test_analysis_intent_integration.py` |
| 第10章 | `backend/tests/test_semantic_loader.py`、`backend/tests/test_metadata_catalog.py` |

> 课程进度更新为 10/19。第 8～10 章的描述以当前 v1.7 安全和 Grounding 实现为准，后续如果语义配置或策略规则变化，需要同步更新对应章节。

### 完成第三部分下半段：LangGraph、修复与多轮分析

> 已完成第 11～12 章，覆盖 `AgentState`、12 个工作流节点、条件边、安全终止、SQL Repair、错误分类、优化建议、LLM 修复回流、会话摘要、SQLite 持久化和澄清恢复。

| 章节 | 主要验证 |
|---|---|
| 第11章 | `backend/tests/test_agent_graph.py` |
| 第12章 | `backend/tests/test_sql_repair.py`、`backend/tests/test_sql_optimizer.py`、`backend/tests/test_conversation_context.py`、`backend/tests/test_session_store.py` |

> 课程进度更新为 12/19。修复和多轮章节明确区分了网络重试、SQL 业务重试和用户重新提问，也明确修复 SQL 必须重新通过 Guard 与权限检查。

### 完成第四部分：产品化能力

> 已完成第 13～15 章，覆盖 JWT/API Key、角色权限、YAML 策略、字段和行级过滤、审计报告、SSE 心跳与取消、查询缓存、LLM Token/成本观测、Prompt 版本、A/B 记录，以及 Vue 三栏工作台、Pinia、Axios、ECharts、表格导出和权限演示。

| 章节 | 主要验证 |
|---|---|
| 第13章 | `backend/tests/test_auth.py`、`backend/tests/test_data_permission_guard.py` |
| 第14章 | `backend/tests/test_query_cache.py`、`backend/tests/test_llm_observability.py` |
| 第15章 | `frontend/tests/`、`npm run build --prefix frontend` |

> 课程进度更新为 15/19。前端章节强调组件只负责展示和交互，认证、权限和安全判定仍以服务器端结果为准。

### 完成第五部分：质量、部署与毕业设计

> 已完成第 16～19 章，覆盖自动化测试分层、NL2SQL 评测集与质量门禁、Docker Compose/Nginx/CI 交付，以及从干净环境复现项目、定位风险和规划后续演进的方法。至此五个部分、十九章正文全部完成。

| 章节 | 主要验证 |
|---|---|
| 第16章 | `backend/tests/test_learning_course_docs.py`、后端单元测试、前端 Vitest |
| 第17章 | `backend/tests/test_evaluator.py`、`backend/tests/test_quality_gate.py` |
| 第18章 | `docker-compose.yml`、`nginx.conf`、`.github/workflows/ci.yml` |
| 第19章 | 文档契约、目录链接、源码路径和从零复现检查 |

> 课程进度更新为 19/19。第一版课程正文已完成；后续项目代码变更时，应按照第 19 章的维护清单同步更新章节和验证证据。
