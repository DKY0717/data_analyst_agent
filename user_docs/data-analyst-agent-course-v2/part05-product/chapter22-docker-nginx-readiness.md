# 第22章 Docker、Nginx 与就绪检查

> 本章预计 1～2 小时，学习从本地代码到可接流量服务的部署证据。Docker 实操为可选外部步骤。

## 22.1 学习目标

> 能区分 build/start/liveness/readiness、demo/secure profile、DuckDB 固定初始化/PostgreSQL Alembic、Nginx SPA/API/SSE代理和 Secret边界。

## 22.2 前置知识

> 会启动前后端，了解容器、volume、端口、环境变量、反向代理和数据库迁移的用途。

## 22.3 为什么需要这一模块

> 进程存活不代表业务表存在、数据非空或安全配置完整；首页可打开也不代表 API 与 SSE代理正常。部署必须以 readiness 和分层验证为准。

## 22.4 输入、输出与依赖

| 配置 | 用途 |
|---|---|
| `docker-compose.yml` | demo DuckDB 前后端 |
| `docker-compose.secure.yml` | 叠加受保护配置 |
| backend/frontend Dockerfile | 镜像构建 |
| `frontend/nginx.conf` | SPA、API、SSE转发 |
| Alembic | PostgreSQL schema生命周期 |

## 22.5 执行流程

```text
compose config → build images → backend start
  → /health/readiness → frontend dependency healthy
  → Nginx static + /api + SSE no-buffer proxy
```

## 22.6 当前代码地图

| 内容 | 路径 |
|---|---|
| Demo Compose | `docker-compose.yml` |
| Secure overlay | `docker-compose.secure.yml` |
| Backend image | `backend/Dockerfile` |
| Frontend image | `frontend/Dockerfile` |
| Nginx | `frontend/nginx.conf` |
| Readiness | `backend/app/api/health.py` |
| Alembic | `backend/alembic/` |

## 22.7 关键代码理解

### 22.7.1 health 与 readiness

> `/health` 只证明 FastAPI 响应；readiness 连接数据库、检查关键业务表与非空数据，并在 secure profile 检查认证和 sandbox 配置。失败对外隐藏数据库原始错误。

### 22.7.2 demo 与 secure

> 默认 Compose 明确设置 `DEPLOYMENT_PROFILE=demo`，适合本地演示，不等于生产模板。secure overlay 应要求认证、强密钥、隔离和受控 Origin；缺条件时 readiness fail closed。

### 22.7.3 两种数据库生命周期

> DuckDB 演示数据可由固定脚本重建，适合可重复 demo；PostgreSQL 使用 Alembic 迁移保留版本演进。不能在生产 PostgreSQL 上用重建演示库替代迁移。

### 22.7.4 Nginx 的三条路由

> `/` 使用 `try_files` 支持 SPA；`/api/` 反代后端并设置长读取超时；精确 SSE 路径使用 HTTP/1.1、关闭 buffering/cache，确保心跳与进度立即透传。

### 22.7.5 Secret 不进入镜像

> Key 通过运行环境注入，不写 Dockerfile、镜像层、构建参数输出或前端 bundle。Compose 展开结果和容器环境同样属于敏感信息，不应贴到公开日志。

## 22.8 最小动手运行

> 工作目录：项目根目录。第一条只解析配置，Docker 可用时不调用模型；pytest 完全离线。

```bash
docker compose config --quiet
pytest backend/tests/test_health.py backend/tests/test_deployment_profiles.py backend/tests/test_migrations.py -q
```

> 如果本机没有 Docker，记录“未执行：缺少容器运行时”，不能写成通过。

## 22.9 故障注入实验

> 使用测试配置指向空临时数据库，比较 `/health` 与 readiness；或在 Compose 测试中缺少 secure 认证配置，确认 fail closed。恢复临时变量，不改正式 `.env`。

## 22.10 调试路径与常见误判

> 顺序：compose config→image build→container state→backend log→readiness→Nginx upstream→浏览器 Network→SSE buffering。容器 healthy 也不证明真实 LLM Key/余额可用；那属于单独外部验收。

## 22.11 独立编码练习

> 写部署前清单：profile、Secret来源、Origin、数据库生命周期、volume权限、sandbox、health/readiness、Nginx SSE、备份与回滚。每项都写证据命令。

## 22.12 测试或评测验证

> 验证 Compose 语义、secure fail-closed、业务表 readiness、Alembic upgrade、前端 build、SSE代理无缓存和 Secret scan。真实 Docker/PostgreSQL应单独注明环境。

## 22.13 面试复述题

> 1. liveness 和 readiness 分别证明什么？
>
> 2. DuckDB重建与PostgreSQL Alembic为什么不能混用？
>
> 3. SSE为什么需要单独的Nginx配置？

## 22.14 掌握度检查与下一章

> 能从浏览器追到容器依赖；能区分demo/secure；能诚实记录外部步骤。下一部分进入测试与评测证据。
