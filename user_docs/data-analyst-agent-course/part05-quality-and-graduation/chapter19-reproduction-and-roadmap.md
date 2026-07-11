# 第十九章 完整复现、项目复盘与继续优化

> 本章对应项目版本 `v1.7`。本章最后核对日期为 2026-07-11。

## 19.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 从干净环境准备 Python、Node.js、数据库和 LLM 配置；
> 2. 按顺序启动后端、前端并完成一次业务查询；
> 3. 验证危险请求、权限阻断和多轮追问；
> 4. 运行测试、评测、Secret Scan 和演示预检；
> 5. 区分已经验证的能力、当前边界和未来扩展；
> 6. 用自己的语言解释这个项目，而不是只复述代码目录。

## 19.2 问题场景：从“能启动”到“能证明”

> 完整复现不是打开首页就结束。一个可交付的复现过程应该同时证明：数据库有正确数据，后端契约可用，业务成功路径可执行，危险和越权路径会阻断，前端可以展示证据，测试和评测可以重复运行。

```text
环境准备
  → 数据库初始化
  → 后端健康/就绪
  → 前端工作台
  → 业务成功路径
  → 安全失败路径
  → 权限对照路径
  → 测试与评测
  → Docker/CI 证据
```

## 19.3 路线一：本地开发复现

### 19.3.1 安装依赖

```bash
cd backend
pip install -r requirements.txt

cd ../frontend
npm install
```

> Python 依赖和 Node 依赖应在各自目录安装。Windows、Linux 和 macOS 的具体虚拟环境命令可以不同，但最终要保证 `pytest`、`uvicorn`、`npm` 和 `vite` 可用。

### 19.3.2 初始化和启动后端

```bash
cd backend
python ../database/seed_data.py
uvicorn app.main:app --reload
```

> 先访问健康和 Schema 接口，确认后端不是只启动了进程而是拥有业务表：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/readiness
curl http://127.0.0.1:8000/api/schema
```

### 19.3.3 启动前端

```bash
cd frontend
npm run dev
```

> 浏览器打开 Vite 输出的地址，确认左侧 Schema 面板能读取表，顶部状态不再停留在 Loading。前端能打开但 Schema 为空时，应先排查后端 API 代理和数据库就绪状态。

## 19.4 配置真实 LLM 的边界

> 真实业务成功路径需要一个可访问的 OpenAI-compatible endpoint。配置 `.env` 时至少确认 API Key、URL 和模型名；不要把真实值写入课程、终端截图或 Git。

```text
QWEN_API_KEY=本地未提交配置
QWEN_API_URL=OpenAI-compatible chat completions endpoint
QWEN_MODEL=当前可用模型
```

> 如果外部端点不可达，仍然可以完成数据库、FastAPI、Guard、权限、前端契约和确定性评测学习。不能把网络错误写成 SQL 逻辑错误，也不能把 Mock 结果写成真实模型质量证明。

## 19.5 核心成功路径

> 在真实模型可用时，先执行一个结果稳定、容易核对的问题：

```text
统计 2024 年每个月的销售额
```

> 观察以下表面：

| 表面 | 应该看到什么 |
|---|---|
| 答案 | 自然语言解释 |
| SQL | 最终经过校验的 SQL |
| 表格 | 列名和结果行 |
| 图表 | 月度趋势或适合的图形 |
| 意图 | 指标、时间维度和过滤 |
| 审计 | Guard、权限、LLM 和执行摘要 |
| 优化 | 可选的规则化建议 |

## 19.6 安全失败路径

> 再验证一个不应该进入数据库的问题：

```text
删除订单表
```

> 预期状态是 `blocked`，命中 `block_destructive_intent` 或相应 SQL Guard 规则；QueryRunner 不应被调用，系统也不应为了“给出答案”而执行任何写操作。

## 19.7 权限对照路径

> 开启本地演示认证后，可以按以下顺序比较 analyst 和 admin：

```text
Analyst：列出客户姓名和注册日期
  → 预期阻断 customers.customer_name

Admin：列出客户姓名和注册日期
  → 预期允许查询
```

> analyst 还可以执行订单销售额问题，但最终 SQL 会应用 `row_filter_region_scope`。观察审计面板中的身份、规则 ID、行过滤和授权 SQL 改写，不要只看页面顶部的角色标签。

## 19.8 多轮追问路径

> 先问一个带指标和时间范围的问题，再使用同一 `session_id` 追问：

```text
第一轮：统计 2024 年每个月的销售额
第二轮：按地区拆一下
```

> 第二轮可以继承上一轮上下文，但不会把完整结果行全部复制到 Prompt。若 SessionStore 不可用或澄清 ID 过期，系统应返回稳定的错误状态，而不是静默使用另一会话的数据。

## 19.9 确定性验证清单

```bash
pytest backend -q
npm run test --prefix frontend
npm run test:e2e --prefix frontend
pytest backend/tests/test_core_path_cases.py -q
cd backend
python -m evaluation.permission_evaluator --json
python -m evaluation.security_audit_exporter --write-report
```

> v1.7 的核心路径回归会用 Fake LLM 替换外部模型，但保留真实 Agent、Guard、权限、隔离 DuckDB 和 SQLite 会话。它适合在没有 API Key 时证明系统编排没有被改坏：

```bash
cd backend
python -m evaluation.core_path_runner
```

> 生产数据库另有迁移往返证据；DuckDB 不使用 Alembic：

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini downgrade base
python -m alembic -c backend/alembic.ini upgrade head
```

> 这些命令覆盖后端回归、前端单测、浏览器、核心路径、权限评测和安全审计导出。E2E、Docker 和真实模型步骤可能需要额外环境，应记录实际是否执行以及失败原因。

## 19.10 面试演示预检和证据包

> `scripts/interview_demo_preflight.py` 检查核心文件、演示环境变量、后端 readiness 和前端页面；`--strict` 遇到失败项返回非零退出码。它不输出 Secret 值。

```bash
python scripts/interview_demo_preflight.py --strict
```

> `scripts/interview_evidence.py` 生成本地测试、离线审计、真实 workflow 查询和 artifact 下载的命令清单。它不联网、不读取 GitHub 登录态，输出的是可复制的证据流程。

```bash
python scripts/interview_evidence.py --run-id <github_run_id>
```

## 19.11 当前项目的能力边界

> 当前项目已经形成较完整的可信 NL2SQL/数据分析 Agent 原型，但复现时应如实说明边界：

| 已验证或具备 | 仍需外部验证或扩展 |
|---|---|
| DuckDB 电商数据和 PostgreSQL 适配 | 大规模企业 Schema 和并发 |
| Intent/SQL/Permission 三层治理 | 专业渗透测试和长期生产运行 |
| SQL Repair、Grounding 和多轮上下文 | 更广泛真实用户问题和外部基准 |
| Vue 工作台、测试、评测和 CI | 分布式队列、多租户和灾备 |
| Docker、readiness 和审计报告 | 真实生产监控、告警和容量规划 |

> “具备生产意识”与“已经经过企业生产验证”不是同一个结论。复盘时要把代码能力、测试证据和未验证假设分开。

## 19.12 项目复盘方法

> 最后不要按文件名背诵，而要回答下面五个问题：

1. 用户问题如何流经前端、API、AgentGraph、数据库和答案生成？
2. 哪些决策由确定性代码完成，哪些交给 LLM？
3. 如果模型生成危险 SQL，哪几层会阻断？
4. 如果 SQL 执行失败，什么错误可以修复，什么错误必须终止？
5. 如何用测试和评测证明一次升级没有破坏核心路径？

> 能够解释这五个问题，说明你开始理解系统的因果关系；只知道“某文件负责某功能”，还不算真正掌握。

## 19.13 毕业设计建议

> 完成基础复现后，可以选择一个边界明确的改造任务作为毕业设计：

| 方向 | 要求 |
|---|---|
| 新业务指标 | 增加语义定义、Grounding、SQL case、黄金结果和前端展示 |
| 新数据源 | 增加连接适配、Schema Loader、权限策略和隔离测试 |
| 更强澄清 | 增加缺失槽位、候选恢复、过期和多轮回归 |
| 结果正确性 | 增加基准数据、比较器、报告和质量门禁 |
| 数据权限 | 增加角色、表列规则、行过滤和越权 E2E |
| 前端能力 | 增加组件、Store、API fixture、Vitest 和 E2E |

> 一个好的毕业任务必须同时包含实现、测试、评测和文档。只增加一个按钮或一个 Prompt，无法证明你理解了完整工程闭环。

## 19.14 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `README.md` | 快速开始和项目边界 | 启动、测试和功能声明 |
| `scripts/interview_demo_preflight.py` | 本地演示预检 | 环境、服务和演示顺序 |
| `scripts/interview_evidence.py` | 证据包清单 | 本地与远端证据链 |
| `backend/evaluation/cases/core_path_cases.yaml` | 核心路径用例 | 成功、权限、安全和澄清 |
| `docs/提升规划.md` | 后续改进方向 | 当前不足与扩展候选 |

## 19.15 动手验证

> 在确认环境准备好后，按本章顺序完成一次复现，并保存以下证据：

```text
1. /health/readiness 响应
2. /api/schema 返回八张业务表
3. 一条业务成功查询的 QueryResponse
4. 一条危险请求的 blocked 响应
5. analyst/admin 权限对照审计
6. 后端和前端测试结果
7. 核心路径或权限评测报告
8. Docker/CI 结果（如果运行条件具备）
```

> 逐项记录命令、时间、代码提交和外部条件。缺少真实 LLM、Docker 或 Playwright 时，应标记为未执行，而不是填写一个推测结果。

## 19.16 常见错误

### 只运行首页截图

> 首页能打开只能证明静态资源可用。必须同时验证 API、数据库、业务结果和安全失败路径。

### 把旧报告当作当前证据

> 检查报告中的 provider、model、HEAD、case pack 和生成时间。代码已经变化时，旧报告只能作为历史参考。

### 发现真实模型不可用就修改安全策略放行

> 网络或配额问题应该记录为外部条件，不能通过关闭 Guard、权限或沙箱来“让演示成功”。确定性测试和离线评测可以继续提供无费用证据。

### 毕业设计只修改 Prompt

> Prompt 修改需要版本、评测 case、结果比较和回归证据，否则无法判断改动是否真的改善系统。

## 19.17 本章小结

> 完整复现的终点不是“程序跑起来”，而是能用稳定证据说明核心成功路径、安全阻断、权限对照、测试评测和交付方式。项目当前已经足够作为工程型学习和求职作品，但真实生产规模、外部数据和长期运行仍需要单独验证。

## 19.18 练习

1. 在没有真实 LLM 的情况下，列出仍然可以完成的确定性验证。
2. 写一份自己的核心路径验收表，至少包含成功、危险、越权和多轮四类。
3. 选择一个毕业设计方向，列出实现、测试、评测和文档四类交付物。
4. 解释为什么一次旧的真实模型报告不能自动证明当前代码质量。
5. 用自己的话讲述本项目最重要的三个工程取舍。

## 19.19 课程完成后的继续学习

> 完成本课程后，可以继续深入 SQL 优化器、数据质量、向量检索、企业身份系统、分布式任务、模型评测和生产可观测性。每次扩展都应沿用本项目已经建立的原则：明确边界、确定性保护、可复现测试和真实证据。
