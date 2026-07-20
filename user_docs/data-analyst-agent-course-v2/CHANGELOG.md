# 课程更新日志

> **首版源码基线：** `8dffc1d76c514c7efe1b6e642ea1880a81989109`

## 2026-07-20

### 建立独立 v2 课程

> 新课程面向具备 Python 基础和简单 SQL、但缺少 Agent 工程经验的学习者。课程不继承旧十九章，而是按照当前系统的依赖关系设计七部分三十二章重建路线。
>
> 首版覆盖截至 2026-07-18 的代码和真实评测证据，包括答案失败隔离、权限与语义修复、分片、原子 checkpoint、严格汇总及 MiMo 超时事故。

### 深化第一部分

> 第1～4章已按当前源码扩展为可学习正文，补充十二节点调用链、Pydantic 与异步基础、八表粒度与重复聚合、DuckDB/PostgreSQL 边界，以及配置、readiness 和脱敏调试流程。对应离线验收为 29 项测试通过。

### 深化第二部分

> 第5～8章已补充双后端 Schema 元数据、FastAPI 请求与业务状态、OpenAI-compatible 调用和最小 NL2SQL 接口。课程明确区分空 content、HTTP 重试、SQL Repair 与结果正确性，并使用 Fake LLM/隔离数据库提供确定性练习。对应专项验收为 72 项测试通过。

### 深化第三部分

> 第9～13章已补充规则/LLM Intent 合并、语义与 MetadataCatalog、Grounding 最短 JOIN 路由、带会话的主动澄清、十二节点条件边、Repair 重新校验、Optimizer 和 SQLite 多轮上下文。正文按当前实现区分危险/越权阻断与可保存的最小执行失败摘要。对应专项验收为 93 项测试通过。

### 深化第四部分

> 第14～18章已补充 Intent/SQL AST 双层 Guard、LIMIT 与子进程超时、JWT/API Key 和 scope-aware 数据权限、行级 SQL 改写、传输/Repair/降级失败分类，以及 AuditReport 与 ContextVar LLM 观测。正文明确 Sandbox 和审计报告的能力边界。对应专项验收为 227 项测试通过。

### 后续同步规则

> 项目代码变化后，先比较当前 HEAD 与本文件基线，再在 `CURRENT-CODE-MAP.md` 定位受影响章节，核对源码、测试和实际行为，最后更新正文、契约测试和本日志。只修改首页版本号不能视为课程已经同步。
