# Data Analyst Agent v1.7 开发说明

## 版本目标

v1.7 把项目从“功能与测试数量较多”收敛为可执行、可审计、可部署验证的求职作品。重点是前后端真实契约、Grounding 路由、权限与 SQL 安全、核心路径证据、生产配置边界和工程门禁。

## 可执行证据

- 15 条核心路径只替换外部模型边界，真实运行 LangGraph、Grounding、Intent/SQL Guard、权限改写、优化器、隔离 DuckDB 和 SQLite 多轮会话。
- 真实模型手动 workflow 记录 HEAD SHA、Provider、模型、脱敏 API 端点、case pack 版本和 UTC 时间，并先运行 4 条 smoke。
- 答案生成异常不会丢弃已完成的 SQL 结果或污染共享缓存；评测 runner 会隔离单 case 异常并继续写出完整失败证据。
- 后端 678 个测试，当前全量覆盖率 81.10%；前端 58 个单元测试和 17 个 Playwright E2E。
- CI 门禁包含 Ruff、ESLint、75% 覆盖率、PostgreSQL migration round trip、Python/Node 依赖审计、Secret Scan、demo/secure Compose、镜像构建和 readiness smoke。

## 数据库生命周期

PostgreSQL 是 Alembic 管理的生产数据库。初始 revision 创建 8 张业务表，CI 在临时 PostgreSQL 执行：

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini downgrade base
python -m alembic -c backend/alembic.ini upgrade head
```

DuckDB 是本地演示与确定性评测数据库，由 `database/init.sql` 和固定种子脚本重建。Alembic 对 DuckDB 显式拒绝，避免用未经验证的方言兼容承诺替代真实迁移证据。

## 部署边界

- `docker-compose.yml` 是明确的 demo profile，默认启用 SQL 沙箱。
- `docker-compose.secure.yml` 是叠加式 secure profile，强制认证、CORS 和模型配置，关闭 Demo Auth。
- secure profile 缺少强 JWT/API Key、启用 Demo Auth 或关闭沙箱时，`/health/readiness` 返回 503。

## 安全与隐私

- LIMIT 对超大常量执行钳制，对动态、负数、`ALL` 和表达式写法 fail-closed。
- 行级权限谓词绑定物理表/别名，并覆盖自连接。
- PostgreSQL 使用事务级 `statement_timeout`，沙箱父进程使用硬超时。
- 公共错误不暴露数据库诊断；Repair 只在内部链路读取详细错误。
- Trace 不记录 SQL 原文或字面量，只记录结构指纹、语句类型和物理表名。
- CSV/Excel 导出会转义公式前缀；Excel 使用纯文本 SpreadsheetML 单元格，并移除存在已知风险的 `xlsx` 依赖。

## 证据解释边界

确定性测试通过不等于真实模型在任意输入上 100% 正确。真实模型结论必须同时给出对应提交 SHA、Provider、模型、case 版本、生成时间和质量门禁报告；缺失任一真实报告时，安全审计严格模式会返回失败。

## v1.8 维护性候选边界

v1.7 冻结前只抽取了独立的进度通知旁路，避免为了缩短文件而改动已经验证的 Agent 拓扑。后续出现对应业务需求或模块继续增长时，再按以下依赖方向拆分：

- `graph.py`：把节点编排与节点业务实现分离，图层只负责状态和条件边。
- `llm_service.py`：把 HTTP transport/retry 与结构化响应解析分离，统一错误和观测边界。
- `data_permission.py`：把 YAML 策略编译与 SQL AST 改写分离，分别测试策略语义和改写正确性。

这些是可维护性演进项，不是当前查询、安全或部署能力的功能缺口。只有出现新 Provider、更多策略类型或新工作流节点等明确需求时才启动，避免面试版本在无业务收益的重构中重新进入施工状态。
