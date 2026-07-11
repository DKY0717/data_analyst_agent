# 第十八章 Docker、Nginx 与持续集成

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 18.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 解释 Dockerfile、镜像、容器、卷和网络的关系；
> 2. 说明后端和前端镜像各自负责什么；
> 3. 理解 Nginx 如何把前端静态文件和 `/api` 请求连接起来；
> 4. 读懂 Docker Compose 的服务、环境变量和健康检查；
> 5. 区分普通 CI、真实模型评测和本地演示预检；
> 6. 理解 Secret Scan 和 artifact 在交付中的作用。

## 18.2 问题场景：在另一台机器复现项目

> 本地运行依赖 Python、Node.js、系统包、环境变量和数据库目录。不同电脑的版本和路径可能不同，导致“在我的机器上可以运行”。Docker 把运行时依赖和启动命令写进镜像/编排配置，CI 再在干净 runner 上重复验证。
>
> Docker 不能自动解决所有问题：LLM Key、数据库持久化和真实模型连通性仍然需要外部配置。教程要把“镜像构建成功”和“真实业务查询成功”分成不同证据。

## 18.3 后端 Dockerfile

> `backend/Dockerfile` 负责安装 Python 依赖、复制后端代码并启动 Uvicorn。镜像内的工作目录、暴露端口和启动命令应该与 Compose 的健康检查一致。

```text
后端镜像
  ├─ Python runtime
  ├─ requirements.txt
  ├─ backend/app
  └─ uvicorn app.main:app
```

> 建议先构建镜像，再运行 `/health/readiness`；如果容器能启动但 readiness 失败，通常说明数据库初始化、环境变量或核心业务表没有准备好。

## 18.4 前端 Dockerfile 和 Nginx

> `frontend/Dockerfile` 通常分为构建阶段和运行阶段：Node.js 安装依赖并执行 Vite build，Nginx 只提供生成的静态文件。这样最终镜像不需要携带 Node.js 开发依赖。
>
> `frontend/nginx.conf` 将 `/api` 和 `/health` 代理到后端容器，并为 Vue Router 的前端路由回退到 `index.html`。浏览器看到的是同源前端地址，API 请求由 Nginx 在容器网络内部转发。

```text
浏览器
  ↓ / 或静态资源
Nginx 前端容器
  ├─ 静态文件
  └─ /api、/health → backend:8000
```

## 18.5 Docker Compose 服务

> `docker-compose.yml` 编排前端、后端和数据卷。后端挂载 DuckDB 数据目录，第一次启动时由 `demo_bootstrap` 创建表并写入种子数据；已存在数据时跳过初始化，避免重启覆盖。

| 配置 | 作用 | 学习时要观察 |
|---|---|---|
| `services` | 定义前后端容器 | 服务名和网络 DNS |
| `environment` | 注入配置 | LLM、数据库、认证和沙箱 |
| `volumes` | 持久化数据 | DuckDB、报告和日志 |
| `depends_on` | 启动依赖 | 是否带健康条件 |
| `healthcheck` | 判断服务就绪 | `/health/readiness` |
| `ports` | 暴露宿主端口 | 浏览器和 API 地址 |

> Compose 服务名是容器网络中的主机名。前端 Nginx 代理后端时使用 `backend:8000`，浏览器不能直接解析这个内部名字。

## 18.6 健康检查和 readiness

> `/health` 只说明进程能响应，`/health/readiness` 还检查数据库连接、业务表和关键演示数据。Compose 应该依赖 readiness，而不是只依赖容器进程已经启动。

```bash
docker compose up -d --build
curl http://localhost/health/readiness
```

> 如果返回非 2xx，先查看后端容器日志和数据卷状态。不要因为前端首页能打开就认为后端业务已经可用。

## 18.7 环境变量和 Secret

> `.env.example` 只描述变量名、默认值和用途，真实 `.env` 不应提交。LLM API Key、JWT Secret、PostgreSQL 密码和成本单价都属于运行时配置。

```text
QWEN_API_KEY=留在本地或 CI Secret 中
JWT_SECRET=不要写入仓库
AUTH_DEMO_ENABLED=false
SANDBOX_MODE=true
```

> demo profile 可以为本地展示提供默认便利，secure profile 应要求强 Secret、关闭不必要的演示入口，并确认 sandbox 和 CORS 配置。配置名称和默认值应以当前 `config.py` 与 Compose 文件为准。

## 18.8 普通 CI

> `.github/workflows/ci.yml` 面向 Pull Request 和 Push，运行确定性后端测试、前端单测、生产构建、Secret Scan、Compose 配置校验、Docker 构建和 readiness smoke test。普通 CI 不向任意 PR 注入真实 LLM Secret，避免测试成本和凭据泄露。

```text
Pull Request / Push
  ↓
后端测试 + 前端测试/构建
  ↓
Secret Scan + Compose 校验
  ↓
Docker 构建 + readiness smoke
```

## 18.9 真实模型评测工作流

> `real-qwen-evaluation.yml` 是手动触发的真实模型工作流，负责运行 NL2SQL、Repair、正确性、Grounding、权限和 Quality Gate，并上传 JSON/Markdown artifact。它和普通 CI 分离，因为真实模型需要 Secret、网络和成本预算。
>
> 真实模型工作流还应该保存 provider、model、commit、运行时间、case pack 版本和执行模式。没有这些元数据，即使报告数字正确，也很难复现或判断它属于哪一次代码。

## 18.10 Secret Scan

> `scripts/check_secrets.py` 只扫描 Git 跟踪文件，命中时输出路径、行号和规则名，不输出 Secret 原文。它不能发现已经写入 Git 历史的凭据，也不能替代平台密钥轮换；它是提交前和 CI 中的一层快速防线。

```bash
git ls-files -z | python scripts/check_secrets.py
```

> 如果扫描失败，先删除源码、Markdown、日志和测试输出中的敏感值，再检查 Git diff 和历史；不要把 Secret 复制到新的“修复提交”中。

## 18.11 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/Dockerfile` | 后端镜像 | 依赖、工作目录、启动命令 |
| `frontend/Dockerfile` | 前端构建和运行镜像 | 多阶段构建、静态资源 |
| `frontend/nginx.conf` | 静态服务和 API 代理 | 同源、路由回退、后端地址 |
| `docker-compose.yml` | 服务和卷编排 | 环境、健康检查、持久化 |
| `.github/workflows/ci.yml` | 普通确定性 CI | 测试、构建、Secret Scan |
| `.github/workflows/real-qwen-evaluation.yml` | 手动真实模型评测 | Secret、报告和 artifact |
| `scripts/check_secrets.py` | 跟踪文件密钥扫描 | 只输出安全摘要 |

## 18.12 动手验证

> 先验证 Compose YAML 和 CI 文件的结构：

```bash
pytest backend/tests/test_workflow_files.py -q
```

> 若本机装有 Docker，再执行：

```bash
docker compose config
docker compose build
docker compose up -d
curl http://localhost/health/readiness
```

> 最后运行 Secret Scan：

```bash
git ls-files -z | python scripts/check_secrets.py
```

> 本机没有 Docker 时，不能把未执行的镜像构建写成通过；可以先完成 YAML、Dockerfile 静态测试，并把实际 Docker 验证交给 CI runner。

## 18.13 常见错误

### Nginx 代理到 `localhost:8000`

> 在前端容器内，`localhost` 指向前端容器自己，不是后端容器。Compose 网络中应该使用服务名 `backend`。

### 健康检查只检查端口

> 端口打开不代表数据库有表或种子数据。使用 `/health/readiness` 检查真实业务依赖。

### 把 `.env` 复制进镜像

> Docker build context 可能把本地 Secret 带入镜像层。通过 `.dockerignore`、运行时 environment 或平台 Secret 注入，构建阶段不复制真实凭据。

### 普通 CI 直接调用真实 LLM

> 这会增加成本、暴露 Secret，并让普通 Pull Request 因外部网络失败。确定性 CI 和手动真实评测工作流应保持边界。

### 容器重启覆盖数据

> 检查 DuckDB 数据卷和 `demo_bootstrap` 的幂等判断。初始化脚本应该只在空库或缺少关键数据时执行。

## 18.14 本章小结

> Docker 把运行时打包，Nginx 把浏览器请求代理到后端，Compose 把服务、配置、健康检查和数据卷连接起来，CI 在干净环境中重复这些验证。真实模型、凭据和持久化数据仍然属于外部运行条件，需要单独管理。

## 18.15 练习

1. 解释为什么前端容器中的 `backend:8000` 和浏览器中的 `localhost` 不能混用。
2. 找出 Compose 中后端 readiness 的检查位置。
3. 说明普通 CI 和真实 Qwen 工作流为什么要分开。
4. 修改一个无关的前端文件，列出它应该触发的 CI 检查。
5. 设计一个不把 `.env` 带进镜像的构建检查。

## 18.16 下一章衔接

> 最后一章会把环境、数据库、后端、前端、核心问题、安全演示、测试和证据包串成一次完整复现，并明确项目当前边界和可以继续扩展的方向。
