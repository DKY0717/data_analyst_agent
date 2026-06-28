# 工作日记

记录每次会话的工作内容，确保项目进度可追溯，不同模型之间可以无缝接手。

---

## 2026-06-10 — 第十次会话

### 完成的工作

**LLM 调用可观测性与成本评测** ✅
- 新增基于 `ContextVar` 的 LLM 调用轨迹，隔离并发异步请求，汇总节点、模型、Token、耗时、API 尝试次数和可选估算成本。
- Qwen API 边界解析 DashScope 真实 usage；失败记录仅保留异常类型，不保存 prompt、请求头、API Key 或完整响应。
- AgentGraph 通过 state 跨节点传递调用轨迹，`audit_report.llm_observability` 返回请求级汇总与调用明细。
- NL2SQL 与 SQL Repair 两套评测报告新增平均调用数、Token、LLM 耗时和成本可用状态。
- 成本单价使用可选环境变量配置，未配置时成本字段保持 `null`。
- 完整后端回归：`124 passed`。
- 真实 Qwen Plus 32 条 NL2SQL 基线：平均每题 `1.78` 次调用、`1889.28 Token`、`9301 ms` LLM 耗时；正常分析执行成功率 `24/24`，危险请求阻断率 `7/8`。
- 真实 Qwen Plus 6 条 Repair 基线：端到端修复 `6/6`，平均每条 `875.67 Token`、`3862.50 ms` LLM 耗时。
- 新增 `docs/Qwen_Plus_LLM调用成本与耗时基线分析.md`，如实记录模型将一条危险请求改写为无害拒绝 SQL 的安全评测边界。
- 阶段提交：`6552eb2`、`ba07018`、`5ab75e3`、`a71456a`、`4a95e5a`。

**GitHub Actions CI 与真实 Qwen 质量门禁** ✅
- 新增 PR/Push 基础 CI，独立运行完整后端测试、前端生产构建和已跟踪文件 Secret Scan，不向普通 PR 注入真实 Qwen Secret。
- 新增手动 `Real Qwen Evaluation` 工作流，支持选择模型、默认告警或 enforce 阈值，并始终发布 Step Summary 与评测 artifact。
- 新增可本地复用的质量门禁 CLI，检查正常分析执行率、危险请求阻断率、安全预期命中率和 Repair 端到端成功率。
- 安全预期命中率阈值使用真实基线精确值 `31/32（0.96875）`，避免展示值 `0.969` 的浮点比较误判。
- 新增 Secret Scan CLI，只扫描 Git 跟踪文件，命中时仅输出路径、行号和规则名，不输出 Secret 原文。
- 两类评测报告写入器支持可选 `EVALUATION_REPORT_DIR`，便于 Actions 将本次报告隔离到 runner 临时目录。
- 完整后端回归更新为 `149 passed`；真实基线在 enforce 模式下通过全部四项质量门禁。
- 阶段提交：`1866455`、`e690d76`、`1f14ac6`、`3b0f561`、`15047fe`、`4ddb14c`。

### 下一步

- 推送 `codex/ci-quality-gates` 分支，在 GitHub 仓库 Secret 中配置 `QWEN_API_KEY`，手动运行一次真实 Qwen 评测工作流。
- 后续可进行版本发布与 LLM 指标持久化监控。

---

## 2026-06-09 — 第九次会话

### 完成的工作

**Qwen Plus SQL Repair 确定性故障注入评测** ✅
- 实现独立 Repair Evaluation Runner，不侵入正常 AgentGraph；固定安全错误 SQL 先通过 Guard，再由真实 DuckDB 确认失败后进入 Qwen Plus Repair。
- 新增 6 类确定性故障 case，覆盖错误字段、错误表、缺失 JOIN、MySQL 日期函数、DuckDB 不支持的季度格式符和地区字段错误。
- 新增 Repair 专属 Markdown/JSON 报告与 7 项指标，包含故障注入、Repair 输出、修复后 Guard、执行、意图保持和端到端修复成功率。
- 第一轮真实基线端到端修复成功率为 `5/6（83.3%）`，失败原因是 `strftime` 字符串参与算术前未显式转换。
- 使用测试驱动补充 Repair prompt 的 DuckDB 季度提取与显式 CAST 约束；相同 6 条用例复测达到 `6/6（100%）`。
- 保留改进前后两份真实报告，并新增 `docs/Qwen_Plus_SQL修复评测基线分析.md`。
- 完整后端回归结果更新为 `110 passed`；格式检查通过，真实评测报告未发现 API Key、Authorization 或 Bearer 信息。
- 相关阶段提交：`f386397`、`80f82ea`。

**SQL Repair 故障注入评测设计** ✅
- 确认采用独立 Repair 评测器，不侵入正常 AgentGraph 生产流程。
- 设计固定安全错误 SQL → 真实 DuckDB 错误 → Qwen Plus Repair → Guard → 执行 → 意图检查的评测链路。
- 明确 6 类确定性故障 case、7 项 Repair 指标、独立中文 Markdown/JSON 报告和安全约束。
- 新增中文设计规格与详细实施计划：
  - `docs/superpowers/specs/2026-06-09-SQL修复故障注入评测设计.md`
  - `docs/superpowers/plans/2026-06-09-SQL修复故障注入评测实施计划.md`

**Qwen Plus 32 条真实评测与安全工作流修复** ✅
- 首次运行 32 条真实评测，发现危险 SQL 被 Guard 阻断后仍进入 Repair，导致危险意图被改写为无关 SELECT 并执行。
- 调整 LangGraph 条件分支：
  - Guard 拒绝后立即终止。
  - SQL Repair 只处理已通过 Guard 但执行失败的 SQL。
- 语义层新增 DuckDB 季度表达式，修复 `%q/%Q` 不受支持导致的季度查询失败。
- 评测报告新增正常分析执行成功率与危险请求阻断率，避免正确安全阻断拉低执行指标。
- 重跑完整 32 条真实评测：
  - 正常分析执行成功率：24/24，100%。
  - 危险请求阻断率：8/8，100%。
  - 安全预期命中率：32/32，100%。
  - SQL 生成成功率：31/32，96.9%；唯一未生成是危险删除请求触发模型拒绝并返回空 SQL。
- SQL Guard 新增空 SQL 明确阻断，模型拒绝危险请求时不再暴露底层解析异常。
- 完整后端回归结果更新为 `98 passed`。
- 新增 `docs/Qwen_Plus_32条评测基线分析.md`，记录问题发现、修复过程和前后基线。

**Qwen Plus 真实端到端验收** ✅
- 将本地 `.env` 的模型配置从 `qwen-turbo` 调整为 `qwen-plus`，密钥仍仅保存在本地忽略文件中。
- 真实调用 DashScope 验证单轮商品销售额分析：
  - SQL 生成、Guard、DuckDB 执行、优化建议、答案生成和审计事件完整贯通。
  - 返回 5 行，重试次数为 0。
- 通过 `/api/chat/query` 验证多轮追问：
  - 首轮统计各地区销售额，第二轮追问“只看前三名”。
  - 第二轮正确继承指标、维度、JOIN 和排序规则，并生成 `LIMIT 3`。
- 验证语义层退款率指标：
  - 正确生成五表关联 SQL，使用退款订单数除以订单数的业务口径。
  - SQL 执行成功，返回 8 个商品类别，并生成完整审计报告。
- 新增 `docs/Qwen_Plus真实端到端验收报告.md`，沉淀真实模型验收证据。

**v0.3 整体收尾与代码审查** ✅
- 审查语义层、评测体系、多轮会话和安全审计相关实现。
- 修复 SessionStore 上下文污染风险：
  - 仅保存通过 SQL Guard 且执行成功的查询轮次。
  - 危险 SQL 和失败查询不再进入下一轮 LLM prompt。
- 修复 AuditReport 阻断规则重复问题：
  - 多次修复重试命中同一规则时，报告摘要只保留一次，事件明细仍完整保留。
- 修复 Pydantic 模型中的可变默认值：
  - 列表和字典改用 `Field(default_factory=...)`。
  - AgentState 模型同步增加审计字段。
- 前端接入 v0.3 后端能力：
  - 工作台持续发送稳定 `session_id`，支持连续追问。
  - 新增 `AuditPanel.vue`，展示安全状态、LIMIT 注入、阻断规则和审计事件。
  - mock fallback 仅在开发环境启用，生产环境不再掩盖真实接口故障。
  - 前端请求超时从 30 秒调整为 120 秒，覆盖完整 Agent 链路。
- 清理并同步文档：
  - v0.3 文档不再保留“下一步做 Phase 1”的过期内容。
  - README、面试稿和前端说明同步到前端多轮会话与审计面板现状。
  - 后端测试数更新为 `95 passed`。

### 验证结果
- `pytest backend/tests/test_session_store.py backend/tests/test_audit_report.py backend/tests/test_query_api.py -q`：12 passed
- `pytest backend/tests -q`：95 passed，5 warnings（FastAPI/TestClient 既有弃用提示）
- `npx vite build --outDir .codex-build --emptyOutDir`：构建成功
- 当前沙箱会回收后台 Vite 子进程，无法完成浏览器视觉检查；临时构建目录和启动日志均已清理。

### 当前进度
- ✅ v0.3 四个核心能力全部完成
- ✅ 后端与前端最小闭环完成
- ✅ 整体代码审查和文档清理完成
- ⏳ 待执行最终验证和 Git 提交

### 下一步
- 运行最终全量测试、前端构建和 `git diff --check`。
- 仅暂存本次项目相关文件，排除 `.superpowers/`、`AGENTS.md`、`identifier.db`、`scripts/` 等原有未跟踪项。
- 创建 v0.3 收尾提交。

---

## 2026-06-03 — 第八次会话

### 完成的工作

**测试环境稳定性修复** ✅
- 修复 `backend/app/utils/logger.py`：logger 在 import 阶段主动创建日志目录；文件日志不可用时保留控制台日志，不再阻断测试收集。
- 新增 `backend/tests/conftest.py`：pytest 启动时创建隔离测试根目录 `backend/tests/.tmp`，初始化独立 DuckDB 测试库，避免依赖真实 `data/database.duckdb`。
- 验证结果：
  - `python -c "from app.utils.logger import logger; print('logger import OK')"` 通过
  - `pytest tests/test_query_runner.py tests/test_schema_loader.py -q`：6 passed
  - `pytest -q`：49 passed

### 当前进度
- ✅ 后端 pytest 已可一键稳定通过
- ⏳ 下一阶段建议升级 SQL Guard 安全深度

### 下一步
- 加强 SQL Guard：表/列白名单、危险 DuckDB 函数拦截、AST 级 LIMIT 注入。
- 再补充安全测试用例，把“LLM 生成 SQL 可控”变成可展示证据。

**SQL Guard 安全升级** ✅
- 修改 `backend/app/security/sql_guard.py`：
  - 支持 `EXPLAIN SELECT`，为后续 SQL 优化分析铺路。
  - 使用 SQLGlot AST 判断顶层 LIMIT，避免字符串字面量中的 `LIMIT` 绕过自动 LIMIT 注入。
  - 拦截 `information_schema`、`pg_catalog` 等系统表访问。
  - 拦截 `read_csv_auto`、`read_parquet`、`duckdb_tables()` 等危险 DuckDB 文件/元数据函数。
- 修改 `backend/tests/test_sql_guard.py`：
  - 新增 6 个安全测试，覆盖 EXPLAIN、系统表、系统函数、文件读取函数、LIMIT 注入边界。
- 验证结果：
  - `pytest tests/test_sql_guard.py -q`：14 passed
  - `pytest -q`：55 passed

### 下一步
- 继续实现真正的 SQL 优化模块：EXPLAIN/执行计划解析、慢查询指标、优化建议生成。
- 或先补一份面试级 README/架构图，把已完成的测试和安全能力讲清楚。

**SQL 优化模块落地** ✅
- 新增 `backend/app/agents/sql_optimizer.py`：
  - 使用 SQLGlot AST 检测 `SELECT *`，提示减少不必要列扫描。
  - 根据 `row_count` 判断结果是否达到返回上限，提示增加过滤条件或分页。
  - 对 SQL 拼接 `EXPLAIN` 后再次经过 SQL Guard 校验，再用 QueryRunner 获取 DuckDB 执行计划。
  - 从执行计划中识别顺序扫描，生成可解释优化建议。
- 修改 `backend/app/agents/graph.py`：
  - 新增 `optimize_sql` 节点。
  - 执行成功后先生成优化建议，再进入答案生成节点。
- 新增 `backend/tests/test_sql_optimizer.py`，并扩展 `backend/tests/test_agent_graph.py`。
- 验证结果：
  - `pytest tests/test_sql_optimizer.py tests/test_agent_graph.py -q`：10 passed
  - `pytest -q`：58 passed
  - 使用隔离测试库 smoke 验证 Optimizer 可生成 `SELECT *` 和顺序扫描建议。

### 下一步
- 修复/重建默认业务库 `data/database.duckdb`，确保本地 smoke 不依赖测试库也能跑通。
- 补充面试级 README：展示测试数、SQL Guard 安全规则、Optimizer 能力和典型问答链路。

**面试级文档补强** ✅
- 更新 `README.md`：
  - 新增项目亮点、核心架构 Mermaid 图、安全策略、SQL 优化建议和面试准备入口。
  - 明确后端当前验证结果为 `58 passed`。
- 新增 `docs/interview_guide.md`：
  - 包含 30 秒项目介绍、简历写法、架构讲解、常见追问回答、演示脚本和技术亮点总结。
- 验证结果：
  - `pytest -q`：58 passed
  - 文档链接检查通过：`docs/interview_guide.md`、`docs/database_design_md.md`、`docs/frontend_workbench_development_notes.md`
  - `git diff --check` 无空白错误，仅有 Windows 换行提示

### 下一步
- 修复/重建默认业务库 `data/database.duckdb`，保证本地后端 smoke 和演示链路稳定。
- 可选：把本轮所有变更整理成 commit，形成一个完整“作品级升级”节点。

**v0.3 开发文档规划** ✅
- 新增 `docs/data_analyst_agent_开发文档_v_0_3.md`：
  - 将 v0.3 定位为“可评测、可解释、可安全审计的企业级 NL2SQL 数据分析 Agent”。
  - 明确四大升级方向：Schema 语义层、SQL 生成评测体系、多轮分析能力、安全审计报告。
  - 给出新版架构、模块拆分、数据结构建议、API 变化、验收标准和实施顺序。
- 更新 `README.md`：
  - 在面试准备入口中加入 v0.3 开发文档链接。
- 验证结果：
  - `docs/data_analyst_agent_开发文档_v_0_3.md` 文件存在。
  - README 关联文档链接目标存在。
  - `git diff --check` 无空白错误，仅有 Windows 换行提示。

### 下一步
- 进入 v0.3 Phase 1：Schema 语义层实施计划。
- 先完成语义层，再启动评测体系、多轮分析和安全审计。

**v0.3 Phase 1 语义层实施计划** ✅
- 新增 `docs/superpowers/plans/2026-06-03-v0.3-语义层实施计划.md`。
- 计划覆盖：
  - 语义层 YAML 配置。
  - `SemanticLoader` 加载器。
  - SQL Generator 语义摘要接入。
  - Qwen SQL prompt 语义层约束增强。
  - README、面试稿和工作日记同步更新。
- 验证结果：
  - 计划文件存在。
  - 占位词扫描无命中。
  - `git diff --check` 无空白错误。

### 下一步
- 按该计划执行 Phase 1，实现 Schema 语义层。

**v0.3 Phase 1: Schema 语义层** ✅
- 新增 `backend/app/semantic/ecommerce_metrics.yaml`：
  - 定义销售额、订单数、客户数、客单价、退款率、复购率等业务指标。
  - 定义月份、地区、商品类别、支付方式等业务维度和 JOIN 关系。
- 新增 `backend/app/semantic/semantic_loader.py` 和 `backend/app/semantic/__init__.py`：
  - 支持按中文别名查找指标/维度。
  - 支持格式化 LLM prompt 语义摘要。
- 修改 `backend/app/agents/sql_generator.py`：
  - `_format_schema()` 输出中合并物理 Schema 和业务语义层。
- 修改 `backend/app/services/llm_service.py`：
  - SQL 生成 prompt 明确要求优先遵循业务语义层中的指标口径、维度定义、默认时间字段和 JOIN 关系。
- 新增/扩展测试：
  - `backend/tests/test_semantic_loader.py`
  - `backend/tests/test_sql_generator.py`
  - `backend/tests/test_llm_service.py`
- 同步更新 `README.md`、`docs/interview_guide.md` 和 `docs/data_analyst_agent_开发文档_v_0_3.md` 的语义层说明与测试数。
- 验证结果：
  - `pytest tests/test_semantic_loader.py tests/test_sql_generator.py tests/test_llm_service.py -q`：26 passed
  - `pytest -q`：66 passed

### 下一步
- 进入 v0.3 Phase 2：SQL 生成评测体系。
- 先设计评测 case 格式，再实现 evaluator 和报告输出。

**v0.3 Phase 2 SQL评测体系实施计划** ✅
- 新增 `docs/superpowers/plans/2026-06-03-v0.3-SQL评测体系实施计划.md`。
- 计划覆盖：
  - 电商 NL2SQL 评测 case YAML，第一版至少 20 条。
  - `EvaluationRunner`：逐条运行 case，计算生成成功率、Guard 通过率、执行成功率、修复成功率、安全预期达成率、平均重试次数和平均执行耗时。
  - `ReportWriter`：输出 JSON 和 Markdown 报告。
  - CLI：`python -m evaluation.evaluator`。
  - README、面试稿和工作日记同步更新。
- 验证结果：
  - 计划文件存在。
  - 占位词扫描无命中。
  - `git diff --check` 无空白错误。

### 下一步
- 按该计划执行 Phase 2，实现 SQL 生成评测体系。

**v0.3 Phase 2: SQL 生成评测体系** ✅
- 新增 `backend/evaluation/cases/ecommerce_nl2sql_cases.yaml`：
  - 共 32 条固定 NL2SQL 评测 case。
  - 覆盖电商指标、维度拆分、安全拦截和 SQL 修复诱导问题。
  - 其中安全 case 至少 8 条，修复 case 至少 5 条，满足 v0.3 验收标准。
- 新增 `backend/evaluation/evaluator.py`：
  - 支持批量运行 case。
  - 计算生成成功率、Guard 通过率、执行成功率、修复成功率、安全预期命中率、平均重试次数和平均执行耗时。
- 新增 `backend/evaluation/report_writer.py`：
  - 输出带时间戳的 Markdown 和 JSON 报告。
  - Markdown 用于面试展示，JSON 用于后续版本对比或自动化分析。
- 新增/扩展测试：
  - `backend/tests/test_evaluation_cases.py`
  - `backend/tests/test_evaluator.py`
  - `backend/tests/test_report_writer.py`
- 同步更新 `README.md`、`docs/interview_guide.md` 和 `docs/data_analyst_agent_开发文档_v_0_3.md`：
  - 将 Phase 2 作为“可评测”亮点写入文档。
  - 后端测试数更新为 `77 passed`。
- 验证结果：
  - `pytest tests/test_evaluation_cases.py tests/test_evaluator.py tests/test_report_writer.py -q`：11 passed
  - `pytest -q`：77 passed
  - `python -c "from evaluation.evaluator import EvaluationRunner; print(len(EvaluationRunner().load_cases()))"`：输出 32
  - `python -c "from evaluation.report_writer import ReportWriter; print(ReportWriter(timestamp='smoke').timestamp)"`：输出 smoke
  - `git diff --check`：无空白错误，仅有 Windows LF/CRLF 提示

### 下一步
- 进入 v0.3 Phase 3：多轮分析能力。
- 建议先实现 `session_id`、内存版 SessionStore 和上下文摘要，再把上下文接入 SQL Generator prompt。
- 真实运行 `python -m evaluation.evaluator` 会调用 Qwen API，需要确认 `.env` 中已配置 `QWEN_API_KEY`。

**v0.3 Phase 3: 多轮分析能力** ✅
- 新增 `docs/superpowers/plans/2026-06-03-v0.3-多轮分析能力实施计划.md`：
  - 明确使用 `session_id`、内存版 SessionStore、ConversationContextBuilder 和 SQL Generator prompt 上下文注入。
- 新增 `backend/app/agents/conversation_context.py`：
  - 从 Agent final state 中提取问题、SQL、结果列、行数、答案摘要和优化建议。
  - 不保存完整 rows，避免上下文过大或污染 prompt。
- 新增 `backend/app/agents/session_store.py`：
  - 基于 `session_id` 保存最近几轮分析摘要。
  - 空 `session_id` 保持单轮查询行为。
- 修改 `backend/app/agents/state.py` 和 `backend/app/agents/graph.py`：
  - AgentState 增加 `session_id` 和 `conversation_context`。
  - `AgentGraph.run(question, session_id=None)` 会读取历史上下文，传给 SQL Generator，并在结束后写回 SessionStore。
- 修改 `backend/app/agents/sql_generator.py` 和 `backend/app/services/llm_service.py`：
  - SQL 生成支持 `conversation_context`。
  - Qwen prompt 明确处理多轮追问，省略指标、维度或过滤条件时继承最近一轮分析意图。
- 修改 `backend/app/models/schemas.py` 和 `backend/app/api/query.py`：
  - `QueryRequest` 和 `QueryResponse` 增加可选 `session_id`。
  - `/api/chat/query` 将 `session_id` 透传给 AgentGraph。
- 新增/扩展测试：
  - `backend/tests/test_conversation_context.py`
  - `backend/tests/test_session_store.py`
  - `backend/tests/test_query_api.py`
  - `backend/tests/test_agent_graph.py`
  - `backend/tests/test_sql_generator.py`
  - `backend/tests/test_llm_service.py`
- 同步更新 `README.md`、`docs/interview_guide.md` 和 `docs/data_analyst_agent_开发文档_v_0_3.md`：
  - 将多轮追问写入项目亮点、API 示例和面试讲法。
  - 后端测试数更新为 `89 passed`。
- 验证结果：
  - `pytest -q`：89 passed，5 warnings（FastAPI/TestClient 既有弃用提示）

### 下一步
- 进入 v0.3 Phase 4：安全审计报告。
- 建议先扩展 SQL Guard 返回结构化 audit events，再让 AgentGraph 汇总生成、修复、LIMIT 注入和执行过程。

**v0.3 Phase 4: 安全审计报告** ✅
- 新增 `docs/superpowers/plans/2026-06-03-v0.3-安全审计报告实施计划.md`：
  - 明确 `AuditReportBuilder`、SQL Guard 审计事件、AgentGraph 汇总和 API 响应透传。
- 新增 `backend/app/agents/audit.py`：
  - 提供 `AuditReportBuilder.make_event()` 和 `build_report()`。
  - 报告包含最终 SQL、安全状态、执行状态、重试次数、LIMIT 注入状态、阻断规则和事件列表。
- 修改 `backend/app/security/sql_guard.py`：
  - Guard 返回新增 `audit_events`、`limit_injected`、`blocked_rule`。
  - 支持记录 `limit_injected`、`block_system_schema`、`block_system_table`、`block_dangerous_function` 等规则证据。
- 修改 `backend/app/agents/state.py` 和 `backend/app/agents/graph.py`：
  - AgentState 增加 `audit_events` 和 `audit_report`。
  - Graph 节点记录 schema 加载、SQL 生成、Guard 校验、SQL 修复、SQL 执行、优化建议和答案生成事件。
  - `run()` 结束后生成最终 `audit_report`。
- 修改 `backend/app/models/schemas.py` 和 `backend/app/api/query.py`：
  - 新增 Pydantic `AuditEvent`、`AuditReport`。
  - `QueryResponse` 增加可选 `audit_report`。
- 新增/扩展测试：
  - `backend/tests/test_audit_report.py`
  - `backend/tests/test_sql_guard.py`
  - `backend/tests/test_agent_graph.py`
  - `backend/tests/test_query_api.py`
- 同步更新 `README.md`、`docs/interview_guide.md` 和 `docs/data_analyst_agent_开发文档_v_0_3.md`：
  - 将安全审计报告写入项目亮点、API 说明、面试讲法和 v0.3 Phase 4。
  - 后端测试数更新为 `92 passed`。
- 验证结果：
  - `pytest tests/test_query_api.py tests/test_agent_graph.py tests/test_sql_guard.py tests/test_audit_report.py -q`：27 passed
  - `pytest -q`：92 passed，5 warnings（FastAPI/TestClient 既有弃用提示）

### 下一步
- v0.3 四个核心能力已经全部落地：语义层、评测体系、多轮追问、安全审计报告。
- 建议下一步做一次整体收尾：运行完整验证、整理 git diff、可选提交；如果继续增强，可以做前端安全审计面板或 CI。

---

## 2026-05-27 — 第六次会话

### 完成的工作

**Task 10: LLM Service** ✅
- 创建了 `backend/app/services/llm_service.py`
- 实现了 `QwenAPIClient` 类，提供三个核心方法：
  - `generate_sql()`: 根据自然语言问题和 Schema 生成 SQL
  - `repair_sql()`: 根据错误信息修复失败的 SQL
  - `generate_answer()`: 根据查询结果生成自然语言解释
- 实现了指数退避重试机制（最大 3 次，2^attempt 秒间隔）
- 实现了 JSON 响应解析，支持从额外文字中提取 JSON
- 实现了查询结果格式化，最多显示 10 条记录
- 添加了中文注释说明各功能模块
- 创建了 `backend/tests/test_llm_service.py` 含 8 个测试用例
- Commit: `a8b9950`

**Task 10 审查发现的问题：**

1. **重试策略不一致** — `LLMResponseError` 和 `LLMError` 直接抛出不重试，只有超时和未知异常才重试。HTTP 429（限流）也应该重试。
2. **import 位置不当** — `import asyncio` 放在 `_call_api` 循环体内部（L134），应移到文件顶部。
3. **超时硬编码** — `DEFAULT_TIMEOUT = 30` 是模块常量，没走 `settings.SQL_TIMEOUT`，无法通过环境变量配置。
4. **`_format_query_result` 截断未告知 LLM** — 最多显示 10 行记录，但 `generate_sql` 的 prompt 里没提这个限制，LLM 不知道结果被截断，可能生成不准确的分析。
5. **JSON 解析边界情况** — `rindex('}')` 取最后一个 `}`，如果 LLM 返回多个 JSON 对象会解析错误。
6. **HTTP 错误未区分** — 非 200 状态码统一抛 `LLMResponseError`，没有区分 429（应重试）和 500（服务端错误）。

**Task 11: SQL Generator Agent** ✅
- 创建了 `backend/app/agents/sql_generator.py`
- 实现了 `SQLGenerator` 类：
  - `generate()`: 调用 `llm_client.generate_sql()` 生成 SQL，返回 `SQLGeneratorOutput`
  - `_format_schema()`: 将 Schema 字典格式化为 LLM 可读文本（含表名、主键、字段类型和可空性）
  - `_extract_columns()`: 使用 SQLGlot 从生成的 SQL 中提取列名（比让 LLM 返回更可靠）
- 与计划的差异：计划使用 `llm_service.call_with_retry()`，实际适配为 `llm_client.generate_sql()`
- 通过 import 检查和 smoke test
- Commit: `5b7235f`

**Task 12: SQL Repair Agent** ✅
- 创建了 `backend/app/agents/sql_repair.py`
- 实现了 `SQLRepairAgent` 类：
  - `repair()`: 调用 `llm_client.repair_sql()` 修复失败的 SQL，返回 `SQLRepairOutput`
  - `_format_schema()`: 与 SQLGenerator 相同的 Schema 格式化逻辑，保持模块独立性
- 通过 import 检查

**Task 13: Answer Generator Agent** ✅
- 创建了 `backend/app/agents/answer_generator.py`
- 实现了 `AnswerGenerator` 类：
  - `generate()`: 调用 `llm_client.generate_answer()` 生成自然语言解释
- 比计划更简洁：`_format_result()` 由 `llm_service.py` 的 `_format_query_result()` 处理，避免重复
- 通过 import 检查

**补充测试：Task 11-13 测试用例** ✅
- 创建了 `backend/tests/test_sql_generator.py`（10 个测试用例）
  - TestFormatSchema: Schema 格式化（3 个）
  - TestExtractColumns: 列名提取（4 个）
  - TestGenerate: SQL 生成（3 个）
- 创建了 `backend/tests/test_sql_repair.py`（6 个测试用例）
  - TestFormatSchema: Schema 格式化（2 个）
  - TestRepair: SQL 修复（4 个）
- 创建了 `backend/tests/test_answer_generator.py`（4 个测试用例）
  - TestGenerate: 答案生成（4 个）
- 创建了 `backend/pytest.ini`，配置 `asyncio_mode = auto`
- 安装了 `pytest-asyncio` 依赖
- 所有 20 个测试通过
- Commit: `9aafe08`

### 当前进度

- ✅ Task 1-13: 已完成（含测试）
- ⏸️ Task 14-20: 待开始

### 下一步

- 完成 Task 14: LangGraph Agent Workflow（backend/app/agents/graph.py + state.py）

---

## 2026-05-31 — 第七次会话

### 完成的工作

**Task 14: LangGraph Agent Workflow** ✅
- `backend/app/agents/state.py` 已存在（上次会话创建），定义了 `AgentState` TypedDict
- 创建了 `backend/app/agents/graph.py`
- 实现了 `AgentGraph` 类，包含：
  - `_build_graph()`: 构建 LangGraph 状态图，注册 6 个节点和条件边
  - `_load_schema`: 加载数据库 Schema
  - `_generate_sql`: 调用 LLM 生成 SQL
  - `_validate_sql`: SQL Guard 安全校验
  - `_execute_sql`: 执行已校验的 SQL
  - `_repair_sql`: 调用 LLM 修复失败 SQL，递增重试计数
  - `_generate_answer`: 调用 LLM 生成自然语言答案
  - `_should_execute`: 校验后条件分支（安全→执行，不安全→修复或终止）
  - `_should_continue`: 执行后条件分支（成功→答案，失败→修复或终止）
  - `run()`: 运行完整工作流的入口方法
- 实现了全局实例 `agent_graph`
- 创建了 `backend/tests/test_agent_graph.py`，含 7 个测试用例：
  - TestAgentGraphHappyPath: 完整正常流程（1 个）
  - TestAgentGraphValidationFailure: 校验失败后修复成功（1 个）
  - TestAgentGraphExecutionFailure: 执行失败后修复成功（1 个）
  - TestAgentGraphMaxRetries: 校验/执行重试耗尽（2 个）
  - TestAgentGraphEdgeCases: 图结构和全局实例（2 个）
- 全部 49 个测试通过（42 已有 + 7 新增）

**Task 15: API Endpoints** ✅
- 创建了 `backend/app/api/health.py`，GET `/health` 健康检查端点
- 创建了 `backend/app/api/schema.py`，GET `/api/schema` 数据库 Schema 查询端点
- 创建了 `backend/app/api/query.py`，POST `/api/chat/query` 核心查询端点
  - 调用 `agent_graph.run()` 运行完整工作流
  - 兼容重试耗尽（answer 为 None）的情况
- 创建了 `backend/app/main.py`，FastAPI 应用入口
  - 注册 CORS 中间件
  - 注册 3 个路由（health、schema、query）
  - 启动时创建 data/ 和 logs/ 目录
- 验证路由注册正确：`/health`、`/api/schema`、`/api/chat/query`
- 全部 49 个测试通过

**前后端联调测试** ✅
- 启动后端服务 `uvicorn app.main:app --port 8001`
- 修复 SchemaResponse 类型不匹配问题（`Dict[str, List]` → `Dict[str, Dict]`）
- 创建数据库并运行种子数据脚本（8 表，304 订单，100 客户）
- 测试 3 个自然语言问题，全部成功：
  - "统计订单总数" → `SELECT COUNT(*) ...` → 304 行
  - "统计2024年每个月的订单数量" → `EXTRACT(MONTH...)` → 12 行
  - "找出销售额最高的5个商品" → CTE 查询 → 5 行
  - "统计各地区的客户数量" → JOIN 查询 → 5 行
- 所有查询通过安全校验，无需重试，执行时间 < 1ms

**前后端联调（通过前端代理）** ✅
- 修改 `frontend/vite.config.js` 代理目标为 `localhost:8001`（8000 被占用）
- 启动后端（8001）和前端（3000）服务
- 通过前端代理测试完整链路：
  - `GET http://localhost:3000/api/schema` → 8 张表 ✅
  - `POST http://localhost:3000/api/chat/query` → SQL + 结果 + 答案 ✅
- 前端 mock fallback 不再触发，使用真实后端数据
- 用户可在浏览器打开 `http://localhost:3000` 进行交互测试

**前端 API 客户端修复** ✅
- 修复 `frontend/src/api/agent.js` 中 `queryAgent` 函数
- 原因：后端返回 `{code, message, data: {...}}`，前端直接 spread `response.data` 导致字段嵌套
- 修复：`response.data` → `response.data.data`

**Task 19: Docker Configuration** ✅
- 创建 `backend/Dockerfile`：Python 3.11 slim + FastAPI
- 创建 `frontend/Dockerfile`：Node 20 构建 + Nginx 托管
- 创建 `frontend/nginx.conf`：静态文件 + API 代理
- 创建 `docker-compose.yml`：编排前后端服务
- 创建 `.dockerignore`：排除 node_modules、__pycache__ 等
- 使用方式：`cp .env.example .env && docker-compose up -d`

**Task 20: Documentation** ✅
- 重写 `README.md`，包含：
  - 核心功能介绍
  - 技术栈表格
  - Docker 和本地开发两种快速开始方式
  - 示例问题
  - API 接口文档
  - 项目结构树
  - 环境变量说明

### 当前进度

- ✅ Task 1-20: 全部完成！

### 本次会话总结

本次会话完成了 Task 14-20 的所有工作：
- Task 14: LangGraph Agent Workflow（7 个测试）
- Task 15: API Endpoints（3 个端点）
- Task 19: Docker Configuration（5 个文件）
- Task 20: Documentation（README）
- 修复：SchemaResponse 类型、前端 API 客户端响应解析
- 验证：前后端联调通过，4 个自然语言问题全部成功

### 后续可优化

- LLM Service 审查遗留问题（重试策略、import 位置等）
- 前端 Element Plus 按需导入减小包体积
- 查询历史持久化
- SQL 优化建议（EXPLAIN ANALYZE）
- 导出查询结果为 CSV/Excel

---

## 2026-05-23 — 第一次会话

### 完成的工作

**Task 1: 项目结构初始化** ✅
- 创建了完整的后端目录结构（backend/app/ 及子目录）
- 创建了所有 __init__.py 文件
- 创建了 .gitignore、.env.example
- 创建了 requirements.txt（含 langgraph 依赖）
- 修复了 .idea/.gitignore 被误提交的问题
- 修复了 frontend/ 和 database/ 目录缺少 .gitkeep 的问题
- Commit: `bdeeb10`

**Task 2: 配置管理** ✅
- 创建了 `backend/app/config.py`，含 Settings 类
- 实现了 `_get_int()` 和 `_get_bool()` 辅助函数
- 修复了 QWEN_API_KEY 验证、BASE_DIR 路径、import 时副作用等问题
- 更新了 .env.example 增加 SQL 配置项
- Commit: `c0a91d6`

**Task 3: 日志配置** ✅
- 创建了 `backend/app/utils/logger.py`
- 实现了控制台(INFO) + 滚动文件(DEBUG, 10MB, 5个备份) 双处理器
- 包含重复处理器防护
- **注意：此任务跳过了 review 流程，用户指出这是错误行为**
- Commit: `446a9d3`

**Task 4: 自定义异常** ✅
- 创建了 `backend/app/utils/exceptions.py`
- 定义了项目基础异常类 AppException
- 定义了数据库、SQL校验、SQL执行、SQL修复、LLM调用等异常类
- 添加了中文注释说明每个异常类的用途
- Commit: `64dd210`

**Task 5: Pydantic模型** ✅
- 创建了 `backend/app/models/schemas.py`
- 定义了请求模型：QueryRequest、SQLValidateRequest、SQLExecuteRequest
- 定义了响应模型：SuccessResponse、ErrorResponse、QueryResponse等
- 定义了Agent内部模型：SQLGeneratorOutput、SQLRepairOutput、AgentState
- 添加了中文注释说明每个模型的用途
- Commit: `90b2db0`
- 修复：为所有模型字段添加中文注释说明字段含义
- Commit: `5c5a0ca`

**Task 6: 数据库连接管理** ✅
- 创建了 `backend/app/db/connection.py`
- 实现了DatabaseConnection类管理DuckDB连接
- 提供了get_connection、close、get_session等方法
- 添加了FastAPI依赖注入函数get_db
- 包含中文注释说明各功能模块
- Commit: `16aa6db`
- 修复：将绝对导入改为相对导入，解决IDE无法识别app模块的问题
- Commit: `789eac8`

**Task 7: Schema加载器** ✅
- 创建了 `backend/app/db/schema_loader.py`
- 创建了 `backend/tests/test_schema_loader.py` 测试文件
- 创建了 `database/init.sql` 数据库初始化脚本
- 实现了 get_tables、get_table_schema、get_full_schema 方法
- 添加了中文注释说明各功能模块
- Commit: `3b86cef`
- 修正：init.sql 与 design.md 保持一致（DECIMAL精度、VARCHAR长度、NOT NULL约束）
- Commit: `42bf259`
- 修复：测试文件和logger.py的导入方式
- Commit: `3308022`

**Task 8: SQL安全校验** ✅
- 创建了 `backend/app/security/sql_guard.py`
- 创建了 `backend/tests/test_sql_guard.py` 测试文件
- 使用SQLGlot进行SQL AST解析
- 支持SELECT、WITH语句，禁止DROP、DELETE、UPDATE等
- 自动添加LIMIT限制
- 添加了中文注释说明各功能模块
- Commit: `e9a2953`

### 遗留问题

- Task 3 的 spec compliance review 和 code quality review 被跳过，用户明确指出这是不对的
- 用户要求创建行为规范 skill 来防止此类问题再次发生

### 创建的 Skill

**全局 Skill（~/.claude/skills/）：**
- `review-discipline` — 强制执行 spec + code quality 两次 review
- `subagent-must-act` — subagent 必须修改代码并 commit，不能只分析
- `commit-after-implementation` — 代码变更后必须立即 commit
- `progress-reporting` — 每个任务完成后输出一行状态更新

**项目级 Skill（skills/）：**
- `sql-safety-rules` — SQL Guard 安全约束
- `qwen-api-patterns` — Qwen API 调用规范
- `agent-workflow-constraints` — LangGraph 工作流规则
- `ecommerce-schema` — 电商业务表结构参考
- `comment-key-steps` — 代码关键步骤写中文注释（用户学习需求）
- `verify-after-write` — 写完代码必须验证再 commit

### 当前进度

- ✅ Task 1: 项目结构初始化
- ✅ Task 2: 配置管理
- ✅ Task 3: 日志配置
- ✅ Task 4: 自定义异常
- ✅ Task 5: Pydantic模型
- ✅ Task 6: 数据库连接管理
- ✅ Task 7: Schema加载器
- ✅ Task 8: SQL安全校验
- ✅ Task 9: Query Runner
- ⏸️ Task 10-20: 待开始

### 下一步

- 完成 Task 10: LLM Service（backend/app/services/llm_service.py）

---

## 2026-05-25 — 第四次会话

### 完成的工作

**前端界面方向设计** ✅
- 阅读了开发文档 v0.2、数据库设计文档和 implementation plan 中的前端/API/数据分析相关内容。
- 与用户确认前端希望兼顾大众审美、可用性和良好用户体验。
- 确定前端方向为“现代 AI 数据分析工作台”，而不是纯聊天页或 BI 大屏。
- 新增设计文档：`docs/superpowers/specs/2026-05-25-frontend-workbench-design.md`。
- 设计范围包括三栏布局、组件划分、数据流、交互状态、图表策略、视觉规范和第一版验收标准。
- 根据用户提醒重新通读 `docs/data_analyst_agent_开发文档_v_0_2.md`，并修订前端 spec，使其明确对齐 v0.2 第 11.1、14、18、23、25 节。
- 修订后的 spec 强调：前端展示不改变推荐开发顺序；如提前实现前端，mock 数据仅用于 UI 预览，最终仍以真实 `/api/chat/query` 联调为准。

### 遗留问题

- 仅完成前端设计方案，尚未开始实现前端工程。
- Visual Companion 启动脚本依赖 bash，本机当前 PowerShell 环境未找到 bash；后续可以直接使用 Vite dev server 进行页面预览。

### 当前进度

- ✅ 前端界面方向已确认
- ✅ 前端设计文档已完成
- ✅ 前端实现计划已完成：`docs/superpowers/plans/2026-05-25-frontend-workbench-implementation.md`
- ⏸️ 前端实现待开始

### 下一步

- 用户 review 前端实现计划。
- 选择 Subagent-Driven 或 Inline Execution 执行方式。
- 实现前端前需要读取 `comment-key-steps` 和 `verify-after-write`。

### 用户偏好

- 前端要兼顾当前大众审美和可用性。
- 界面应好看、好用、用户体验好。

---

## 2026-05-25 — 第五次会话

### 完成的工作

**前端工作台实现** ✅
- 创建分支：`codex/frontend-workbench`。
- 搭建 Vue 3 + Vite + Element Plus + Pinia + Axios + ECharts 前端工程。
- 实现 `frontend/src/api/agent.js`，支持 `/api/chat/query` 调用和 mock 数据兜底。
- 实现 `frontend/src/stores/query.js`，管理 question、loading、result、error、history。
- 实现工作台组件：自然语言输入、示例问题、查询历史、Schema 简览、结果解释、图表、结果表格、SQL 面板和优化建议面板。
- 组合三栏工作台页面，视觉方向对齐“现代 AI 数据分析工作台”。
- 运行 `npm run build` 通过；浏览器打开 `http://localhost:3000` 验证页面可渲染，控制台无 error。
- 根据用户学习需求新增说明文档：`docs/frontend_workbench_development_notes.md`，记录本次前端开发做了什么、文件作用、验证方式和推荐学习顺序。
- Commits:
  - `ab731a2` feat: scaffold Vue frontend
  - `73c20ff` feat: add frontend query state
  - `7230d1d` feat: add workbench sidebar components
  - `a3c9fcf` feat: add analysis result components
  - `76d716b` feat: compose frontend workbench
  - `a716391` feat: compose frontend workbench
  - `2f0ad4a` docs: update work diary for frontend workbench

### 遗留问题

- 当前后端 `/api/chat/query` 尚未完整联调，前端会使用 mock fallback。
- Vite build 存在 chunk size 警告，主要来自 Element Plus + ECharts，第一版可接受，后续可做按需加载优化。
- 查询历史第一版仅前端内存保存。

### 当前进度

- ✅ 前端第一版工作台已完成
- ⏳ 等后端 Agent/API 完整后进行真实接口联调

### 下一步

- 后端完成 `/api/chat/query` 后，使用真实响应验证 SQL、表格、图表和优化建议展示。
- 如需减少前端包体，可引入 Element Plus 按需导入和 ECharts 动态加载。

---

## 2026-05-25 — 第三次会话

### 完成的工作

**项目熟悉与状态确认** ✅
- 阅读了 `AGENTS.md`、`logs/work-diary.md`、开发文档 v0.2、数据库设计文档和 implementation plan。
- 梳理当前实现：Task 1-9 已完成，后端已有配置、日志、异常、Pydantic 模型、DuckDB 连接、Schema Loader、SQL Guard、Query Runner 和种子数据脚本。
- 确认前端目前仅有 `.gitkeep`，API、LangGraph Agent、LLM Service 尚未实现。
- 运行现有测试：沙箱内因 `logs/app.log` 权限导致 pytest 收集失败；沙箱外重跑 `pytest` 通过，结果为 14 passed。

### 遗留问题

- `pytest` 在 Codex 沙箱内会因为 `RotatingFileHandler` 打开 `logs/app.log` 权限失败；业务测试本身在沙箱外通过。
- Git 工作区存在未跟踪文件：`AGENTS.md`、`identifier.db`、`scripts/`，本次未修改。

### 当前进度

- ✅ Task 1-9: 已完成并有测试覆盖
- ⏸️ Task 10: LLM Service 待开始
- ⏸️ Task 11-20: 待开始

### 下一步

- 实现 Task 10: `backend/app/services/llm_service.py`
- 开始前读取 `qwen-api-patterns`、`comment-key-steps`、`verify-after-write`
- 实现后运行最小验证，并按用户要求完成 review 与 commit
- 按照 subagent-driven development 流程执行
- 必须完成 spec review + code quality review
- 写完代码后验证再 commit
- 关键步骤写中文注释

### 用户偏好

- 需要详细解释关键步骤
- 使用 conda 管理 Python 环境
- DuckDB 优先
- 严格遵循开发文档阶段
- 使用 Qwen API（DashScope）
- 代码关键步骤需要中文注释（学习需求）
- 每次写完代码必须验证再 commit

### 今日总结

- 完成了项目初始化（Task 1-3）
- 建立了完整的行为规范体系（全局 4 个 + 项目级 7 个 skill）
- 创建了工作日记机制，确保跨模型工作连续性
- Python 环境要求：3.10+
- 会话结束时间：2026-05-23

---

## 2026-05-24 — 第二次会话

### 完成的工作

**Task 9: Query Runner** ✅
- 创建了 `backend/app/db/query_runner.py`
- 实现了 QueryRunner 类，提供 `execute(sql)` 方法
- 返回结构化结果：success、columns、rows、execution_time_ms、row_count
- 查询失败时返回错误信息而非抛出异常
- 注：DuckDB 不支持 `statement_timeout`，已移除该设置
- 创建了 `backend/tests/test_query_runner.py` 含3个测试用例
- Commit: `09690e6`

**附加：种子数据脚本** ✅
- 创建了 `database/seed_data.py` 生成电商业务模拟数据
- 生成：10个地区、8个类别、40个商品、100个客户
- 生成：304个订单、797条订单明细、304条支付、53条退款
- 固定随机种子(42)保证数据可复现
- Commit: `09690e6`

### 当前进度

- ✅ Task 1-9: 已完成
- ⏸️ Task 10-20: 待开始

### 下一步

- 完成 Task 10: LLM Service（backend/app/services/llm_service.py）
# 2026-06-11 — v0.4 Intent Guard 与危险意图评测

## 完成内容

- 新增确定性 Intent Guard，覆盖数据修改、凭据访问、系统访问、安全绕过和批量敏感导出五类规则。
- 将 `check_intent` 接入 LangGraph 唯一入口，危险请求在 Schema/Qwen/数据库前终止，并写入审计报告。
- API 稳定返回 Intent 状态和 HTTP 200 阻断响应，日志与异常路径不泄露原始危险问题。
- 新增 37 条危险意图固定 case、中文 Markdown/JSON 报告和 CI 退出码。
- NL2SQL 评测区分 Intent Guard 与 SQL Guard 阻断阶段。
- 普通 CI 接入确定性 Intent Evaluation，真实 Qwen 质量门禁升级为四项指标 100%。

## 最终验证

- 后端：216 passed
- 前端：production build 成功，保留既有 chunk size 警告
- Secret Scan：通过
- Intent Evaluation：阻断率 100%，安全通过率 100%，误杀率 0%，规则匹配率 100%
- Qwen Plus NL2SQL：正常分析 24/24，危险请求阻断 8/8，Intent/SQL Guard 各阻断 4 条
- Qwen Plus SQL Repair：6/6
- 强制质量门禁：通过

## 关键提交

- `bd8508d` 至 `d47beaa`：Intent Guard 实现与边界加固
- `37ccc9e`、`43c01f4`：LangGraph Intent Gate
- `e50459a`：稳定阻断 API
- `4282769`、`5c5a9c6`：危险意图评测与报告
- `959e4c0`：分层阻断指标
- `586f6f0`：CI 与质量门禁

---

## 2026-06-11 — v0.5 结果正确性黄金基准

### 完成的工作

- Task 1：建立 10 条黄金 case 与参考 SQL ✅
  - 锁定人工审核参考 SQL、比较契约和固定断言。
  - 退款率空分母统一返回稳定数值 `0.0`。
  - 规格审查通过；10/10 参考 SQL 通过 SQL Guard 并可在固定 DuckDB 执行。
  - Commit：`2b0ee3c`、`46e527d`、`0d735b9`

### 当前进度

- ✅ Task 1：建立 10 条黄金 case 与参考 SQL
- ✅ Task 2：实现 ReferenceQueryRunner
  - 参考 SQL 必须先通过 Guard，只执行非空 `sanitized_sql`。
  - Guard 和执行器畸形返回均严格 fail-closed。
  - 本模块使用稳定错误消息，不向报告传播敏感异常文本。
  - Commit：`f98c22f`、`1b614b0`、`33ae97b`
- ✅ Task 3：实现 ResultComparator
  - 支持 unordered、ordered、top_n、scalar 四种比较模式、数值容差与固定断言。
  - 真实比较无损，差异摘要严格限量，容差匹配保留全局最优匹配语义。
  - Commit：`95f588e`、`6175535`、`9fa104b`、`ad4782a`
- ✅ Task 4：实现 ResultCorrectnessEvaluator
  - 使用可注入 Agent、ReferenceQueryRunner 和 ResultComparator 独立评估结果正确性。
  - 单条失败稳定分类且不中断整批；报告结果不保存完整结果集。
  - 汇总结果正确率、列/值/排序匹配率、核心业务指标准确率和参考查询健康指标。
  - 定向及相关回归：`91 passed`。
  - Commit：`e655f54`
- ✅ Task 5：验证参考 SQL 与固定断言
  - 10 条参考 SQL 全部经过 SQL Guard 并在固定种子 DuckDB 上执行成功。
  - 参考结果列与 required_columns 一致，固定业务断言全部通过。
  - 种子脚本支持注入隔离连接并在每次入口重置随机种子，pytest 不再依赖本地业务库。
  - 完整后端回归：`315 passed`。
  - Commit：`ed5a527`
- ✅ Task 6：输出中文结果正确性报告
  - 新增 CorrectnessReportWriter，同时输出 UTF-8 JSON 与中文 Markdown。
  - 报告展示八项正确性/参考查询指标，失败明细最多五条。
  - JSON 与 Markdown 均过滤未知结果字段，不写入完整大结果集。
  - ResultCorrectnessEvaluator CLI 已接入报告输出。
  - 定向测试：`12 passed`。
  - Commit：`7a9ad84`
- ✅ Task 7：接入手动真实 Qwen Workflow
  - 正确性评测位于真实 NL2SQL/Repair 评测之后、质量门禁之前。
  - 复用统一报告目录和 artifact 上传，第一版只记录基线，不阻塞普通 PR。
  - Workflow 契约测试：`2 passed`。
  - Commit：`a1efae7`
- ✅ Task 8：文档、真实 Qwen 基线与最终验收
  - 首轮真实 Qwen Plus 正确率 `5/10（50%）`，发现四条输出别名漂移和一条商品类别销售额重复聚合。
  - 未放宽比较标准；语义层新增稳定英文输出别名和商品类别粒度覆盖表达式，SQL 生成 prompt 同步强化。
  - 相同 10 条 case 复测达到 `10/10（100%）`，八项结果正确性指标全部为 `100%`。
  - 新增 v0.5 开发文档，并同步 README、面试稿、工作日志和前后两份真实报告。
  - 最终后端：`319 passed`；前端 production build 成功；Intent Evaluation 和 Secret Scan 全部达标。
  - 基线修复 Commit：`b53a0b2`

### 下一步

- 推送当前 main 的 v0.5 提交，手动运行 GitHub `Real Qwen Evaluation` 验证云端 artifact。
- 下一阶段可建设 Schema Context Manager，并使用 v0.5 黄金基准约束正确率不能回退。

### 云端验收补充

- 推送 v0.5 后，基础 CI 成功，但 GitHub 将 `Real Qwen Evaluation` 判定为无效工作流。
- 根因是 job 级 `env` 使用了 runner 分配后才可用的 `runner.temp` 上下文。
- 将 `EVALUATION_REPORT_DIR` 移到评测、质量门禁和摘要 step 的环境变量，并增加 Workflow 回归测试。
- 定向回归：`7 passed`。
- 修复后首次云端真实评测发现 runner 缺少固定 DuckDB；新增可重复执行的评测库重建脚本，在评测前创建表结构并写入固定种子，同时增加数据库与 Workflow 顺序契约测试。
- 云端 runner 使用模块方式执行评测库脚本，确保仓库根目录位于 Python 模块搜索路径。
- 修复 Linux pytest 收集时的根目录导入差异：评测库脚本自行定位仓库根目录，测试通过文件路径加载，不依赖调用器的 `sys.path`。

---

## 2026-06-15 — v0.6 分层分析意图与 Schema Grounding 设计

### 完成的工作

- 确认 v0.6 采用可解释混合分层架构：安全意图、结构化分析意图、Schema Grounding、图路由、风险决策、主动澄清和裁剪 Context。
- 主动澄清同时支持候选按钮与自由文本，最终归一化为稳定候选 ID；最多两轮且恢复任务前重新执行安全检查。
- 确认项目内研究增强数据集先行，v0.7 再适配 Spider、BIRD 等公开数据集。
- 确认严格发布门禁：任一核心指标未达标，禁止发布 `v0.6.0`。
- 已完成并自审正式设计文档：`docs/superpowers/specs/2026-06-15-v0.6-hierarchical-intent-schema-grounding-design.md`。

### 下一步

- 用户审核正式设计文档。
- 审核通过后编写逐任务、TDD 驱动的 v0.6 实施计划。

### 设计审核后进展

- 用户确认继续实施规划。
- 已将 v0.6 拆分为四个连续里程碑和十五个 TDD 任务，覆盖稳定契约、意图解析、Grounding、图路由、主动澄清、分层评测、消融实验和严格发布门禁。
- 实施计划：`docs/superpowers/plans/2026-06-15-v0.6-hierarchical-intent-schema-grounding-implementation.md`。

### 实施进展

- ✅ Task 1：建立跨层稳定数据契约
  - 新增 AnalysisIntent、Grounding、SchemaRoute 和 ClarificationRequest 等 Pydantic 契约。
  - 稳定候选 ID、关键文本、置信度和最多两轮澄清均有模型级边界校验。
  - TDD RED 已确认模块缺失；GREEN 契约测试 `5 passed`，相关回归 `18 passed`。
  - 完成规格符合性与代码质量两轮审查。
- ✅ Task 2：扩展 Schema Loader 并构建 Metadata Catalog
  - Schema Loader 从 DuckDB 约束目录输出结构化主外键，并将表名查询改为参数化。
  - 语义层为指标、维度和粒度覆盖增加稳定候选 ID，同时保持现有 Prompt 兼容。
  - Metadata Catalog 合并物理 Schema、业务语义与规范 Join 边，并返回隔离副本。
  - TDD RED 已确认 Catalog 缺失；定向测试 `15 passed`，完整后端回归 `330 passed`。
  - 完成规格符合性与代码质量两轮审查。
- ✅ Task 3：实现高确定性规则意图解析器
  - 基于语义目录解析显式指标与维度别名，按文本首次出现位置稳定排序并去重。
  - 使用有限正则解析年份、排序方向和 Top-N，未知指标显式写入 missing slots。
  - TDD 捕获并修复 `前 3` 空格边界；定向测试 `12 passed`，完整后端回归 `334 passed`。
  - 完成规格符合性与代码质量两轮审查。
- ✅ Task 4：实现 LLM 意图解析器与候选合并器
  - Qwen Client 新增结构化分析意图调用，Prompt 禁止输出 SQL、物理表名和内部推理。
  - LLM Parser 使用 Pydantic 契约校验响应，结构错误不传播模型原始内容。
  - Merger 合并规则与 LLM 候选，规则高确定性槽位优先，冲突显式保留并降低置信度。
  - TDD RED 已确认模块缺失；定向测试 `20 passed`，完整后端回归 `339 passed`。
  - 完成规格符合性与代码质量两轮审查。

---

## 2026-06-24 — 项目体检与面试打磨规划

### 完成的工作

- 读取项目工作日记、README、面试稿、v0.6 设计/实施计划、近期 Git 提交和关键代码。
- 确认当前代码已推进到 v0.6 后续提交：`0b42f84 feat: complete v0.6 system - grounding, clarification, lifespan, chunking`。
- 运行当前基础验证：
  - 后端全量测试：`349 passed, 1 warning`。
  - 前端 production build：通过，保留 Element Plus/ECharts 大 chunk 警告。
  - Secret Scan 正确命令：`git ls-files -z | python scripts/check_secrets.py`，扫描 207 个 tracked files，通过。
  - Intent Evaluation：37 条 case 全部通过。
- 发现当前主要风险：
  - README 和面试稿仍停留在 v0.5/`319 passed`，未同步 v0.6 分层意图和 Schema Grounding。
  - v0.6 主动澄清目前仅展示 `clarification`，主流程没有暂停执行、冻结意图或按 `candidate_id` 恢复。
  - `parse_intent` 节点聚合了意图解析、Grounding 和澄清检查，不如设计文档中分层节点清晰。
  - 前端首屏自动提交查询，真实 Qwen 配置存在时会产生一次非用户主动触发的模型调用。

### 当前进度

- ✅ 完成项目现状体检。
- ✅ 完成第一轮问题定位。
- ⏳ 等待用户确认打磨路线后进入实施。

### 下一步

- 推荐优先做“面试稳态打磨”：补齐 README/面试稿/v0.6 开发文档，修复前端自动调用和澄清交互的最小闭环，再考虑更大规模拆分 LangGraph 节点与分层评测。
- 实施前需要按流程确认方案，然后编写/更新计划，逐项 TDD 实现、测试、审查并提交。

### 实施补充

- 完成主动澄清最小闭环：
  - AgentGraph 在明确模糊且可恢复的低置信请求上，于 SQL 生成前暂停。
  - SessionStore 保存 pending 澄清请求，并用稳定 `candidate_id` 恢复原问题。
  - API 新增 `status`、`clarification` 和澄清回答字段。
  - 前端点击澄清候选时提交结构化 `clarification_id` + `candidate_id`。
- 修复前端首屏自动真实查询问题：
  - 首页只加载 Schema，不再打开页面就触发 Qwen 调用。
- 同步面试资料：
  - README 测试数更新为 `356 passed`。
  - 新增 `docs/data_analyst_agent_开发文档_v_0_6.md`。
  - 更新 `docs/interview_guide.md`，补充分层意图、Schema Grounding 和主动澄清讲法。
- 验证结果：
  - `pytest -q`：`356 passed, 1 warning`。
  - `npm run build`：通过，保留既有 Element Plus/ECharts 大 chunk 警告。
  - `git ls-files -z | python scripts/check_secrets.py`：207 个 tracked files 通过。

### 当前进度

- ✅ 面试稳态打磨第一轮完成。
- ✅ 主动澄清从展示态升级为可暂停、可恢复的最小闭环。
- ⏳ 后续可继续拆分 LangGraph v0.6 节点，并建设分层意图/Grounding 专项评测集。

### 第二轮打磨补充

- 将 v0.6 主链路拆成更清晰的 LangGraph 节点：
  - `parse_intent`：只负责规则/LLM 意图解析与候选合并。
  - `ground_schema`：只负责 Schema Grounding 与路由证据。
  - `assess_clarification`：只负责主动澄清决策。
- 新增节点级测试，确保 parse 不再隐式承担 Grounding/澄清职责。
- 同步 README、v0.6 开发文档和面试稿中的链路说明。
- 验证结果：
  - `pytest -q`：`361 passed, 1 warning`。

### 当前进度

- ✅ LangGraph v0.6 节点拆分完成。
- ⏳ 后续建议建设分层意图/Grounding 专项评测集，量化槽位 F1 与 Grounding Top-K 命中率。

### 第三轮打磨补充

- 新增 v0.6 分层意图/Grounding 确定性专项评测：
  - Case 文件：`backend/evaluation/cases/intent_grounding_cases.yaml`。
  - Runner：`backend/evaluation/intent_grounding_evaluator.py`。
  - 报告器：`backend/evaluation/intent_grounding_report_writer.py`。
  - 测试：`backend/tests/test_intent_grounding_evaluator.py`。
- 评测指标覆盖槽位整体匹配率、Grounding 候选命中率、路由表召回率、澄清决策准确率、澄清候选命中率和全部预期满足率。
- CLI 验证：`python -m evaluation.intent_grounding_evaluator` 输出 7 条 case 全部通过，六项指标均为 `100%`。
- 全量验证：`pytest -q` 为 `367 passed, 1 warning`；`npm run build` 通过；Secret Scan 扫描 212 个 tracked files 通过。
- Commit：`e036a28`。

### 当前进度

- ✅ v0.6 分层链路已有独立、离线、可展示评测。
- ⏳ 后续可扩充更多口语化、多意图和候选冲突 case。

### 第四轮打磨补充

- 将 v0.6 分层意图/Grounding 评测接入普通 CI：
  - PR 和 main push 除后端测试、前端构建、Secret Scan、Intent Evaluation 外，还运行 `python -m evaluation.intent_grounding_evaluator`。
- 扩展手动 `Real Qwen Evaluation`：
  - 真实 NL2SQL、Repair、结果正确性之后运行 Grounding 评测。
  - `quality_gate` 新增 `--correctness-report` 和 `--intent-grounding-report`。
  - 质量门禁同时要求结果正确率和 v0.6 Grounding 六项核心指标达到 `100%`。
- 新增/更新 workflow 与质量门禁契约测试，使用 TDD 先确认缺口失败，再补实现。
- 验证结果：`pytest tests/test_quality_gate.py tests/test_workflow_files.py -q` 为 `25 passed`；`pytest -q` 为 `374 passed, 1 warning`；`npm run build` 通过。
- Commit：`f5af759`。

### 当前进度

- ✅ v0.6 Grounding 不只是离线报告，已经进入 CI 与发布质量门禁。
- ⏳ 后续可继续扩充 Grounding case，或增加主动澄清消融实验来量化澄清价值。

### 第五轮打磨补充

- 新增主动澄清消融实验：
  - Runner：`backend/evaluation/ablation_runner.py`。
  - 测试：`backend/tests/test_ablation_runner.py`。
  - CLI：`python -m evaluation.ablation_runner`。
- 四种模式固定为 `full`、`without_rule_parser`、`without_graph_router`、`without_clarification`。
- 当前 7 条 Grounding case 上，完整链路分层预期满足率为 `100%`；禁用主动澄清后为 `85.7%`，主动澄清带来 `14.3` 个百分点提升。
- 验证结果：`pytest tests/test_ablation_runner.py tests/test_intent_grounding_evaluator.py -q` 为 `10 passed`；`pytest -q` 为 `378 passed, 1 warning`；`npm run build` 通过；Secret Scan 扫描 214 个 tracked files 通过。
- Commit：`fb28407`。

### 当前进度

- ✅ 主动澄清已有可量化消融证据，能回答“为什么不是让模型直接猜 SQL”。
- ⏳ 后续建议扩充更多歧义 case，并考虑把消融摘要写入独立 Markdown 报告。

---

## 2026-06-28 — 简历项目体检

### 完成的工作

- 根据用户问题评估项目是否适合作为 Agent 开发简历项目。
- 阅读并抽查 README、面试稿、LangGraph 主链路、质量门禁、CI、前端配置和工作日记。
- 运行验证：
  - `npm run test`：33 passed。
  - `npm run build`：通过，仍有既有大 chunk 警告。
  - `pytest -q`：失败，原因是 backend 根目录下未跟踪临时脚本 `test_mimo.py`、`test_mimo_direct.py` 被 pytest 收集并调用真实 LLM，API Key 无效。
  - `pytest tests -q`：456 passed, 3 failed, 1 warning。

### 发现的问题

- 当前不是“一键全绿”状态，直接展示给面试官前需要修复。
- 未跟踪临时文件 `backend/test_fix.py`、`backend/test_mimo.py`、`backend/test_mimo_direct.py`、`backend/test_parse.py` 会污染 pytest 收集。
- 主测试集 3 个失败：
  - `block_subquery_leak` 安全 case 缺少 `expected_tables` 或 `expected_metrics`。
  - `customer_count_by_region` 黄金基准固定断言未匹配。
  - `test_prepare_evaluation_database_rebuilds_repeatably` 仍断言旧种子规模，与当前 5500+ 订单数据不一致。
- 工作区存在未跟踪报告、Playwright 结果和本地数据库文件，求职展示前应清理或加入忽略规则。

### 当前判断

- 项目作为 Agent 简历项目的技术含金量合格，亮点包括 LangGraph 分层链路、双层安全、SQL Repair、结果正确性黄金基准、Grounding 评测、消融实验、CI 和前端工作台。
- 但当前仓库交付面不合格：测试命令和 README 宣称不完全一致，临时文件未清理，少量测试与数据规模变更不同步。

### 下一步

- 清理或移动 backend 根目录临时 `test_*.py` 文件。
- 修复 3 个后端失败测试，使 `pytest tests -q` 全绿。
- 再运行 `pytest -q`、`npm run test`、`npm run build` 和 secret scan。
- 同步 README/面试稿中的测试数量与实际结果。

### 后端深度补充评估

- 抽查后端核心实现：LangGraph 主链路、SQL Guard、Intent Guard、分层意图契约、Grounding、LLM Service、SSE API、QueryRunner、沙箱执行、结果正确性评测、Grounding 评测、消融实验、认证、限流、追踪和缓存。
- 结论：后端在 Agent 编排、安全治理、评测体系和可解释链路上明显强于普通简历项目；核心亮点是把 NL2SQL 从“生成 SQL”推进到“可控执行、可修复、可评测、可审计”。
- 主要短板：生产化仍是作品级，认证未强制接入查询接口，CORS 全放开，沙箱默认未启用，Schema Grounding 当前更多依赖语义配置和规则召回，测试/数据/文档存在少量不同步。

### 收尾实施

- 清理 backend 根目录临时 `test_*.py`，避免全量 pytest 收集手工 LLM 验证脚本。
- 将 `block_subquery_leak` 补齐安全 case 的期望表和指标。
- 将黄金结果基准和数据库重建测试同步到当前固定种子规模：
  - 地区 30、商品 200、订单 5511、退款 718。
  - 客户地区统计 6 行、合计客户数 1000。
  - 2024 平均客单价 `1324.3111230521224`。
  - 复购率 `1.0`。
  - 月度订单数合计 `5511`。
- 测试环境设置 `OTEL_EXPORTER=none`，并让 none 模式仍创建 recording span，消除 pytest 结束后的 ConsoleSpanExporter 异步写出异常。
- `.gitignore` 增加本地工具目录、Playwright 输出、identifier.db 和评测报告生成文件。
- 文档同步后端测试数到 `459`，并将示例 API Key 改为安全占位符。

### 最终验证

- `pytest -q`：459 passed, 1 warning。
- `npm run test`：33 passed。
- `npm run build`：通过，保留既有 chunk size 警告。
- `git ls-files -z | python scripts\check_secrets.py`：289 个 tracked files 通过。
- `git diff --check`：通过，仅有 Windows LF/CRLF 提示。

---

## 2026-06-28 — v0.7 生产化权限治理设计

### 完成的工作

- 根据用户“继续”确认进入下一版优化。
- 明确 v0.7 第一阶段聚焦“认证 + 角色级表/字段权限 + 审计闭环”，不在本阶段纳入查询历史持久化和行级权限。
- 新增设计规格：`docs/superpowers/specs/2026-06-28-v0.7-production-auth-governance-design.md`。
- 设计重点：
  - 查询接口接入 `get_current_user`。
  - 新增 `DataPermissionGuard`，在 SQL Guard 之后、QueryRunner 执行之前做 SQL AST 权限检查。
  - `admin`、`analyst`、`support` 三类内置角色。
  - 权限阻断进入 `audit_report.events` 和 `blocked_rules`，且不进入 SQL Repair。
  - 未启用认证时保留本地开发兼容模式。

### 当前进度

- ✅ v0.7 方向确认。
- ✅ 设计文档已完成并自审，无占位符命中。
- ✅ 用户已确认设计。
- ✅ 新增 TDD 实施计划：`docs/superpowers/plans/2026-06-28-v0.7-production-auth-governance-implementation.md`。

### 下一步

- 按实施计划进入代码实现：先写 `DataPermissionGuard` 红灯测试，再依次接入 AgentGraph、API 认证、审计报告和文档。
- 每个里程碑完成后运行定向测试，最终运行 `pytest -q`、`npm run test`、`npm run build`、Secret Scan 和 `git diff --check`。
