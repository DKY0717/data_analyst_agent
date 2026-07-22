# 第4章 环境、配置与调试方法

> 本章预计 1～2 小时，建立“先收集证据、再修改代码”的固定习惯。不要在文档、命令历史或截图中暴露真实密钥。

## 4.1 学习目标

> 能检查工作目录、解释器、依赖、环境变量、数据库、端口、日志与异常堆栈；区分启动配置、运行配置和安全部署约束；形成最小复现。

## 4.2 前置知识

> 会用 PowerShell 或终端执行命令，知道环境变量只是一种进程输入。无需调用真实模型。

## 4.3 为什么需要这一模块

> Vibe Coding 项目最常见的浪费是把环境问题改成代码问题：导入失败就修改路径、401 就改 Prompt、端口占用就改 API、数据库为空就怀疑 LLM。固定排查顺序能保护正确代码不被误改。

## 4.4 输入、输出与依赖

| 配置组 | 代表字段 | 影响 |
|---|---|---|
| 应用 | `APP_HOST`、`APP_PORT`、`DEBUG` | 服务监听与调试 |
| 部署 | `DEPLOYMENT_PROFILE`、CORS | demo/secure 行为 |
| 认证 | `AUTH_*` | 登录与管理端点保护 |
| 数据库 | `DATABASE_URL`、`DATABASE_BACKEND` | DuckDB/PostgreSQL 连接 |
| 模型 | `QWEN_API_KEY`、`QWEN_API_URL`、`QWEN_MODEL` | OpenAI-compatible 调用 |
| SQL | `SQL_TIMEOUT`、`SQL_MAX_ROWS`、`SQL_MAX_RETRIES` | 资源与修复边界 |
| 安全 | `SANDBOX_MODE`、权限策略路径 | 隔离与授权 |
| 日志 | `LOG_LEVEL` | 可观测细节 |

> `QWEN_*` 是兼容性变量名，当前默认 endpoint/model 可以指向 MiMo。变量名不等于供应商事实，排障必须同时记录 URL 主机、model 和实际响应，但要脱敏。

## 4.5 执行流程

```text
记录现象与时间
  → 确认 cwd / interpreter / dependency
  → 确认实际配置（脱敏）
  → 确认 database / port / process
  → 运行最小离线测试
  → 再检查外部 LLM
  → 形成根因与回归证据
```

> 只有在最小离线路径正常后，才值得花费网络和 API 费用测试真实模型。否则多个变量会同时变化。

## 4.6 当前代码地图

| 内容 | 路径 | 关注点 |
|---|---|---|
| 配置示例 | `.env.example` | 可配置项，不含真实值 |
| Settings | `backend/app/config.py` | 解析、默认值与路径 |
| 应用生命周期 | `backend/app/main.py` | 启动初始化 |
| 日志 | `backend/app/utils/logger.py` | 日志级别与输出 |
| 异常 | `backend/app/utils/exceptions.py` | 内外错误边界 |
| readiness | `backend/app/api/health.py` | 数据库与 secure fail-closed |
| 部署测试 | `backend/tests/test_deployment_profiles.py` | profile 契约 |

## 4.7 关键代码理解

### 4.7.1 Settings 在导入时读取环境

> `Settings` 类属性通过 `os.getenv` 构造，模块末尾的 `settings` 是进程内配置对象。测试里临时修改环境变量后，若模块已经导入，旧对象不一定自动变化；应按测试设计重载模块或构造隔离配置，不能据此认定环境变量无效。

### 4.7.2 默认值不是安全生产值

> 本地 DuckDB、demo 行为或空认证值可以帮助开发启动，但 secure profile 的 readiness 会检查认证与沙箱等条件并 fail closed。生产部署不能因为 `/health` 返回 200 就绕过 readiness。

### 4.7.3 路径通常相对进程工作目录

> 默认 `DATABASE_URL` 是 `duckdb:///./data/database.duckdb`。相对路径与当前工作目录有关；项目同时使用 `BASE_DIR`、`DATA_DIR` 约束部分目录。遇到“数据库不存在/为空”时先打印已解析绝对路径。

### 4.7.4 错误分类比错误文案更重要

| 证据 | 常见层级 |
|---|---|
| 401/403 | 凭据或权限 |
| 429 | 限流或配额 |
| DNS/连接拒绝 | 网络、URL、代理、端口 |
| 422 | Pydantic 请求校验 |
| SQL parser/column error | SQL Guard 或数据库 |
| reasoning 有值、content 为空 | 供应商响应/兼容性与重试 |

> 不要在对外响应中返回完整堆栈、数据库 URL、Authorization 或供应商原文。内部日志也只记录必要摘要和 request ID。

## 4.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```powershell
Get-Location
python --version
python -c "from backend.app.config import settings; print(settings.DEPLOYMENT_PROFILE, settings.QWEN_MODEL, settings.DATABASE_BACKEND)"
pytest backend/tests/test_health.py backend/tests/test_deployment_profiles.py -q
```

> 输出模型名可以，绝不要输出 `settings.QWEN_API_KEY`。若项目使用专用虚拟环境，还要记录 `Get-Command python` 的来源。

## 4.9 故障注入实验

> 可恢复实验：只在当前 PowerShell 进程设置非法整数，启动一个新的 Python 进程导入配置，观察回退/解析行为；随后删除该进程变量。不要修改 `.env`。

```powershell
$env:APP_PORT = 'not-a-number'
python -c "from backend.app.config import settings; print(settings.APP_PORT)"
Remove-Item Env:APP_PORT
```

> 第二个实验可把 `DEPLOYMENT_PROFILE` 设为非法选择，观察 `_get_choice` 如何处理，再恢复环境。所有实验都应先写预期，再看结果。

## 4.10 调试路径与常见误判

### 后端启动失败

> 依次确认 cwd、Python 路径、依赖导入、端口占用、配置解析、数据库目录权限；只有堆栈进入业务模块后才分析业务代码。

### API 能访问但查询失败

> 保存 request ID 与响应类型；区分 422/401/429/5xx；检查 audit/trace 的最后成功阶段；再决定查看 LLM、SQL 或数据库。

### 前端页面异常

> 先看浏览器 Network 的 URL、状态和响应，再看 Pinia 状态和组件。Vite 代理错误与后端 Agent 错误不是一类问题。

### 常见误判

> `.env.example` 只是模板，不会自动成为 `.env`；修改 `.env` 后已有进程不会自动加载；`/health` 成功不代表 readiness；模型超时不证明 API Key 无效；SQL Repair 失败也不等于网络失败。

## 4.11 独立编码练习

> 为“后端启动但 readiness 失败”写一张调查表，包含现象、时间、cwd、解释器、profile、数据库绝对路径、端口、HTTP 状态、最后成功阶段、敏感信息是否脱敏、最小复现和恢复步骤。

## 4.12 测试或评测验证

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
pytest backend/tests/test_health.py backend/tests/test_deployment_profiles.py backend/tests/test_seed_data.py -q
```

> 验收时不仅记录 pass/fail，还要写清三个测试组分别证明 readiness、部署 profile 和数据库初始化的什么行为。外部模型只在后续明确标注的章节主动验证。

## 4.13 面试复述题

> 1. 如何证明故障来自模型供应商，而不是 SQL 或数据库？
>
> 2. 为什么修改环境变量后当前进程可能仍使用旧值？
>
> 3. `/health` 和 `/health/readiness` 为什么不能合并成同一个含义？

## 4.14 掌握度检查与下一章

> 能用固定顺序定位目录、配置、端口与数据库问题；能描述一次不泄密的最小复现；能解释 demo 与 secure profile。完成后进入数据库连接与 Schema Loader。
