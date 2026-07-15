# Data Analyst Agent

自然语言驱动的数据库分析系统。用中文提问，系统自动生成安全 SQL、执行查询、修复错误，并返回自然语言解释和交互式图表。

## 项目亮点

**12 节点 LangGraph Agent 工作流** — 不是简单调 API，而是完整的有向图编排：意图解析 → Schema Grounding → 主动澄清 → SQL 生成 → SQL 安全校验 → 数据权限校验 → 执行 → 自动修复 → 优化建议 → 答案生成。

**三层安全治理** — Intent Guard 在 LLM 调用前阻断危险意图，SQL Guard 在 AST 层面校验生成的 SQL，Data Permission Guard 在执行前按 YAML 策略检查角色级表/字段权限并注入行级过滤。确定性基准覆盖破坏性操作、凭据访问、系统表访问、文件读取和敏感字段越权访问。

**SQL 自动修复闭环** — 执行失败后将错误信息反馈给修复 Agent，根据错误类型选择差异化修复策略，最多重试 3 次，每次修复后重新经过安全校验。

**600+ 后端测试 + 可执行核心路径** — 后端 672 个测试、前端 58 个单元测试、17 个 E2E 测试、65 条结构化评测用例、6 条数据权限回归评测和 15 条可执行核心路径覆盖关键功能与安全链路；当前全量后端覆盖率基线为 81.01%。

## 面试/简历材料

- [面试讲述稿](docs/interview_guide.md)：用于面试前快速复习项目架构、核心追问、演示路径和不足边界。
- [简历项目包装包](docs/resume_project_packet.md)：用于复制简历 bullet、30/90 秒介绍、STAR 故事、演示清单和证据索引。
- 面试前可运行 `python scripts/interview_demo_preflight.py --strict` 做面试演示预检，确认演示环境变量、核心文件、本地后端 readiness 和前端页面状态。
- 面试前可运行 `python scripts/interview_evidence.py --run-id <github_run_id>` 生成本地测试、真实模型 workflow 和 `security-audit-*.md/json` artifact 的证据包清单。

### 核心路径黄金问题

v1.7 将面试和回归最常用的问题收敛到 `backend/evaluation/cases/core_path_cases.yaml`。Runner 只替换外部模型边界，真实执行 LangGraph、Grounding、Guard、权限、优化器、隔离 DuckDB 和 SQLite 多轮会话，覆盖成功、澄清、权限和安全失败路径。可以运行：

```bash
cd backend && python -m evaluation.core_path_runner
```

## 核心架构

```mermaid
flowchart LR
    Q[用户问题] --> Auth[Auth<br/>JWT / API Key]
    Auth --> Intent[Intent Guard<br/>NLP 层拦截]
    Intent -->|安全| AI[意图解析<br/>+ Schema Grounding]
    Intent -->|危险| Block[提前阻断]
    AI --> Clarify{需要澄清?}
    Clarify -->|是| Ask[返回候选<br/>等待用户选择]
    Clarify -->|否| G[SQL Generator<br/>LLM 生成 SQL]
    G --> Guard[SQL Guard<br/>SQLGlot AST 校验]
    Guard -->|不安全| Block
    Guard -->|安全| Perm[Data Permission Guard<br/>策略权限 + 行级过滤]
    Perm -->|无权限| Block
    Perm -->|通过| Exec[Query Runner<br/>DuckDB 执行]
    Exec -->|失败| Repair[SQL Repair<br/>错误分类 + 差异化修复]
    Repair --> Guard
    Exec -->|成功| Opt[SQL Optimizer<br/>EXPLAIN 分析]
    Opt --> Ans[Answer Generator<br/>LLM 生成答案]
    Ans --> SSE[SSE 流式推送<br/>实时进度]
    SSE --> UI[Vue 工作台<br/>图表 + 表格 + Markdown]
```

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Vue 3 + Vite + Element Plus + Pinia + ECharts + vue-router |
| 后端 | FastAPI + LangGraph + SQLGlot + slowapi + PyJWT |
| 数据库 | DuckDB（嵌入式）/ PostgreSQL（生产） |
| LLM | MiMo v2.5 Pro（兼容 OpenAI API） |
| 测试 | pytest + Vitest + Playwright |
| 部署 | Docker + GitHub Actions CI/CD |

## 功能清单

### 后端

- 自然语言转 SQL（LangGraph 12 节点工作流）
- Intent Guard + SQL Guard + Data Permission Guard 三层安全治理
- 角色级表/字段权限（admin / analyst / support，越权 SQL 不执行、不修复）
- YAML 数据权限策略 + 行级 SQL 过滤（执行前由后端 AST 改写，不依赖 LLM）
- SQL 自动修复（错误分类 + 差异化策略 + 最多 3 轮重试）
- 分层意图解析 + Schema Grounding（指标/维度映射）
- 主动澄清机制（模糊问题暂停，返回候选等待用户选择）
- 多轮分析追问（session_id 上下文复用）
- SSE 流式响应（asyncio.Queue 真实进度推送）
- LLM 调用可观测性（Token、耗时、成本统计）
- JWT Token + API Key 双模式认证（未配置密钥时保持本地开发放行）
- 速率限制（slowapi，默认 30 次/分钟）
- PostgreSQL Alembic upgrade/downgrade；DuckDB 演示库由固定 init.sql 重建
- 结构化审计报告（身份摘要、权限可观测性、Guard 命中、LIMIT 注入、修复事件）

### 前端

- 三栏工作台布局（输入 / 结果 / SQL 详情）
- SSE 流式进度条（真实阶段 + 百分比）
- ECharts 交互式图表（柱状 / 折线 / 饼图 / 散点 + 多列数据支持）
- Markdown 答案渲染（marked）
- 表格分页（50 行/页）+ CSV / Excel XML 导出（公式前缀转义 + 文本单元格）
- 暗色模式切换
- 查询收藏（localStorage 持久化）
- 历史记录面板
- vue-router 路由（查询结果可通过 URL 分享）
- 响应式布局（桌面端 / 平板端 / 移动端）
- 权限演示工作台（admin / analyst / support 一键切换，审计面板展示身份、authorization 事件和数据权限摘要）

### 评测体系

| 评测 | 用例数 | 可复核证据 |
|------|--------|----------|
| NL2SQL 电商评测 | 32 条 | 手动真实模型 workflow 产出；以 artifact 的 HEAD SHA 为准 |
| 危险意图评测 | 37 条 | 确定性 case pack 覆盖阻断与安全对照 |
| Intent Guard 提前阻断 | 8 条 | 确定性提前阻断回归 |
| SQL Repair 故障注入 | 6 条 | 手动真实模型 Repair 报告 |
| 结果正确性黄金基准 | 10 条 | 人工参考 SQL + 确定性结果比较 |
| 分层意图 + Grounding | 7 条 | 槽位、表路由和 JOIN 边精确评测 |
| 数据权限评测 | 6 条 | 权限决策、规则、行过滤和 admin 对照 |
| 结构化评测用例 | 65 条 | 覆盖 11 个类别 |

## 快速开始

### 方式一：Docker（推荐）

```bash
git clone <repo-url>
cd data_analyst_agent
cp .env.example .env
# 编辑 .env，填入 QWEN_API_KEY
docker-compose up -d
# 前端: http://localhost
# API 文档: http://localhost:8000/docs
```

Docker 前端通过 Nginx 将 `/api` 和 `/health` 同源代理到后端容器；本地开发时 Vite 将 `/api` 代理到 `http://localhost:8000`。
Docker 后端启动时会在空 DuckDB 数据卷中自动建表并写入演示数据；已存在数据时会跳过初始化，避免重启覆盖持久化数据。

生产式配置使用 secure overlay；缺少强 JWT/API Key、沙箱、CORS 或模型配置时，Compose/readiness 会 fail-closed：

```bash
docker compose -f docker-compose.yml -f docker-compose.secure.yml up -d
```

### PostgreSQL 迁移与质量门禁

Alembic 只管理 PostgreSQL 生产结构，避免把 DuckDB 方言差异伪装成双后端迁移。CI 在临时 PostgreSQL 执行 `upgrade -> downgrade -> upgrade`：

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini downgrade base
python -m alembic -c backend/alembic.ini upgrade head
```

普通 PR CI 还会执行 Ruff、ESLint、后端 75% 覆盖率门槛、Python/Node 依赖审计、Secret Scan、secure Compose 解析、镜像构建与 readiness smoke。真实模型调用仍放在手动 workflow，并输出 HEAD SHA、Provider、模型、脱敏端点、case 版本和 UTC 时间，避免把旧 artifact 当作当前提交证据。
`/health/readiness` 不只检查数据库连接，还会验证核心业务表和关键演示数据，避免空库或 seed 失败时误报可用。
基础 CI 会运行前端单元测试和前端生产构建，避免前端测试数量只停留在 README 声明。
基础 CI 会运行 Playwright 前端 E2E 测试，覆盖工作台基础交互、响应式布局和权限演示链路。
基础 CI 会校验 Docker Compose 编排配置，提前发现服务、环境变量和健康检查配置漂移。
基础 CI 会真实构建后端和前端 Docker 镜像，防止 Dockerfile、构建上下文或前端 Nginx 代理配置漂移。
基础 CI 会启动后端容器并请求 `/health/readiness` 做 smoke test，验证容器启动、空 DuckDB 数据卷自举和 readiness 链路。

### 方式二：本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
python ../database/seed_data.py
uvicorn app.main:app --reload

# 前端（新终端）
cd frontend
npm install
npm run dev
```

### v0.8 权限演示工作台

本地演示角色切换需要在 `.env` 中开启：

```bash
JWT_SECRET=dev-demo-secret-change-me-32-bytes
AUTH_DEMO_ENABLED=true
```

前端顶部身份条支持 `admin`、`analyst`、`support` 三种演示身份。普通查询和 SSE 查询都会携带 `Authorization: Bearer <token>`，权限阻断会在安全审计面板中展示身份摘要、authorization 事件、数据权限摘要和阻断规则。

面试前建议先运行面试演示预检。脚本会检查演示环境变量、核心文件、本地后端 readiness 和前端页面状态；`--strict` 模式遇到失败项会返回非零退出码：

```bash
python scripts/interview_demo_preflight.py --strict
```

#### 30 秒面试演示路径

1. 在顶部身份条点击 `Analyst`，确认当前身份显示为 `demo:analyst`。
2. 提交 `统计 2024 年每个月的销售额`，展示分析结果正常返回。
3. 提交 `列出客户姓名和注册日期`，展示请求被数据权限策略阻断。
4. 打开右侧安全审计，指出 `demo:analyst`、`authorization blocked`、`row_filter_region_scope`、`block_unauthorized_column` 和被阻断字段 `customers.customer_name`。
5. 切换为 `Admin`，再次提交同一客户姓名问题，展示管理员查询成功。

这条演示路径说明：Agent 不只会生成 SQL，还能在最终 SQL 执行前做角色级字段权限校验和行级过滤，并把允许、改写、阻断证据写入审计报告。

### v1.0 权限策略外部化

Data Permission Guard 从 `backend/app/security/data_permissions.yaml` 加载角色表/字段权限，并在执行前对需要行级隔离的角色自动注入 SQL 行过滤条件。比如 analyst 查询订单销售额时，后端会在最终 SQL 执行前加入区域范围过滤；审计报告只展示命中的规则 ID 和表名，不泄露完整策略表达式。

### v1.1 权限可观测性和评测

每次查询的 `audit_report` 会汇总 `permission_observability`，直接展示是否经过权限检查、是否允许、命中的阻断规则、引用表字段、行级过滤规则 ID，以及最终 SQL 是否被权限层改写。权限评测可在不调用 LLM、不连接真实数据库的情况下回归验证 admin / analyst / support 的关键安全场景：

```bash
cd backend
python -m evaluation.permission_evaluator --json
```

GitHub Actions 会在基础 CI 中运行 deterministic permission evaluation；手动真实模型工作流也会把权限评测报告纳入 quality gate，确保 6 条权限 case 的决策、规则、行级过滤和 SQL 改写没有回退。

### v1.3 安全审计报告导出

安全审计导出命令会把 Intent Guard、Schema Grounding、Data Permission Guard、可选真实评测报告和 quality gate 结果汇总为 JSON / Markdown 两份材料。默认模式不调用真实 LLM、不连接真实数据库，适合本地面试演示和版本交付审计：

```bash
cd backend
python -m evaluation.security_audit_exporter --write-report
```

如果已经有真实评测报告，也可以把 `nl2sql-evaluation-*.json`、`sql-repair-evaluation-*.json`、`result-correctness-evaluation-*.json` 和 `quality-gate.json` 传入同一份审计报告。报告会明确区分“已验证通过”和“未提供真实评测输入”，避免把缺失输入误写成 0 分或通过。

导出的 `security-audit-*.md` 会包含“输入完整性”表，直接列出真实评测报告和 Quality Gate 是否已纳入。默认命令适合面试现场快速展示确定性安全审计；严格交付检查可以加上 `--fail-on-missing-real-reports`，要求真实评测输入齐全，否则命令返回非零退出码：

```bash
cd backend
python -m evaluation.security_audit_exporter --write-report \
  --nl2sql-report evaluation/reports/nl2sql-evaluation-<timestamp>.json \
  --repair-report evaluation/reports/sql-repair-evaluation-<timestamp>.json \
  --correctness-report evaluation/reports/result-correctness-evaluation-<timestamp>.json \
  --quality-gate-report evaluation/reports/quality-gate.json \
  --fail-on-missing-real-reports
```

手动触发的真实模型 workflow 会先生成运行元数据和 4 条核心 smoke，再运行完整 NL2SQL、SQL Repair、结果正确性、Grounding、权限评测和 quality gate，最终把 `security-audit-*.md/json` 与其它报告一起上传为 artifact。报告绑定当前 HEAD SHA，面试或复盘时可以确认它确实对应当前代码。

面试前可以用轻量证据包脚本生成可复制命令清单。脚本只输出本地/远端证据检查步骤，不联网、不读取 GitHub 登录态：

```bash
python scripts/interview_evidence.py --run-id <github_run_id>
```

## 运行测试

```bash
# 后端测试（672 个）
cd backend && python -m pytest -q

# 前端单元测试（58 个）
cd frontend && npm run test

# E2E 测试（17 个）
cd frontend && npm run test:e2e

# 权限演示 E2E（Mock 后端响应，不依赖真实 LLM）
cd frontend && npm run test:e2e -- permission-demo.spec.js

# 评测用例
cd backend && python -m evaluation.evaluator

# 数据权限评测（不调用 LLM，不连接真实数据库）
cd backend && python -m evaluation.permission_evaluator --json

# 安全审计报告导出（不调用 LLM，不连接真实数据库）
cd backend && python -m evaluation.security_audit_exporter --write-report
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/query` | 自然语言查询 |
| POST | `/api/chat/query/stream` | SSE 流式查询 |
| GET | `/api/schema` | 数据库 Schema |
| GET | `/health` | 存活检查 |
| GET | `/health/readiness` | 就绪检查（验证数据库连接、核心业务表和关键数据） |
| GET | `/health/cache` | 缓存统计（启用认证时需 admin JWT 或 API Key） |
| GET | `/health/metrics` | 综合监控指标（启用认证时需 admin JWT 或 API Key） |
| GET | `/health/ab-tests` | A/B 测试列表（启用认证时需 admin JWT 或 API Key） |
| POST | `/health/ab-tests` | 创建 A/B 测试（启用认证时需 admin JWT 或 API Key） |
| POST | `/api/auth/demo-login` | 本地演示角色登录（需 `AUTH_DEMO_ENABLED=true`） |
| POST | `/api/auth/login` | 可选密码登录（默认关闭，需显式配置管理员账号） |
| GET | `/api/auth/me` | 当前用户信息 |

```bash
# 查询示例
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question": "统计 2024 年每个月的销售额"}'

# 多轮追问
curl -X POST http://localhost:8000/api/chat/query \
  -d '{"session_id": "demo", "question": "按地区拆一下"}'
```

## 项目结构

```
data_analyst_agent/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI 路由
│   │   ├── agents/        # LangGraph Agent 工作流
│   │   ├── db/            # 数据库连接和 Schema 加载
│   │   ├── semantic/      # 业务语义层
│   │   ├── security/      # Intent Guard + SQL Guard + Data Permission + Auth + Rate Limit
│   │   ├── services/      # LLM 服务 + 追踪 + 可观测性
│   │   ├── models/        # Pydantic 模型
│   │   └── utils/         # 日志和异常
│   ├── evaluation/        # 评测 cases、runner 和报告
│   ├── alembic/           # PostgreSQL Alembic revisions
│   └── tests/             # 672 个测试
├── frontend/
│   ├── src/
│   │   ├── api/           # API 客户端
│   │   ├── components/    # 12 个 Vue 组件
│   │   ├── stores/        # Pinia 状态管理
│   │   └── views/         # 页面视图
│   ├── e2e/               # Playwright E2E 测试
│   └── tests/             # Vitest 单元测试
├── database/
│   ├── init.sql           # 表结构
│   └── seed_data.py       # 5500+ 订单种子数据
├── docker-compose.yml
└── .github/workflows/     # CI/CD 流水线
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QWEN_API_KEY` | LLM API Key | **必填** |
| `QWEN_API_URL` | LLM API 地址 | MiMo API |
| `QWEN_MODEL` | 模型名 | `mimo-v2.5-pro` |
| `SQL_TIMEOUT` | 查询超时（秒） | `30` |
| `SQL_MAX_ROWS` | 最大返回行数 | `1000` |
| `SQL_MAX_RETRIES` | SQL 修复最大重试 | `3` |
| `SANDBOX_MODE` | SQL 执行子进程沙箱开关 | `false` |
| `JWT_SECRET` | JWT 签名密钥（可选，启用时至少 32 字符） | 留空=禁用认证 |
| `API_KEYS` | 逗号分隔的 API Key（可选） | 留空=禁用 |
| `AUTH_DEMO_ENABLED` | 本地演示角色登录开关 | `false` |
| `AUTH_PASSWORD_LOGIN_ENABLED` | 密码登录开关 | `false` |
| `AUTH_ADMIN_USERNAME` / `AUTH_ADMIN_PASSWORD` | 密码登录管理员账号 | 空 |
| `CORS_ALLOW_ORIGINS` | 逗号分隔的前端来源白名单 | 本地前端地址 |
| `DATA_PERMISSION_POLICY_PATH` | 数据权限策略 YAML 路径；留空使用默认策略 | 留空 |
| `RATE_LIMIT_QUERY` | 查询端点限流 | `10/minute` |
| `DATABASE_BACKEND` | 数据库后端 | 自动检测 |

## License

MIT
