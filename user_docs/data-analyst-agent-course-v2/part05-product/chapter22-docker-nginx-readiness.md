# 第22章 Docker、Nginx 与就绪检查
> 本章预计 1～2 小时，学习项目从本地进程到可交付服务的部署链路。
## 22.1 学习目标
> 能区分存活、就绪、依赖健康和反向代理问题。
## 22.2 前置知识
> 会启动前后端，了解端口、环境变量和 HTTP 请求。
## 22.3 为什么需要这一模块
> “进程启动了”不等于“服务可接流量”；数据库、认证隔离和依赖配置必须在 readiness 中被验证。
## 22.4 输入、输出与依赖
> 输入是镜像、环境变量和依赖服务；输出是前端静态站点、后端 API 与健康状态。
## 22.5 执行流程
```text
compose → backend/frontend containers → Nginx proxy → /health/readiness
```
## 22.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 容器编排 | `docker-compose.yml` |
| 后端镜像 | `backend/Dockerfile` |
| 前端镜像 | `frontend/Dockerfile` |
| Nginx | `frontend/nginx.conf` |
| 健康路由 | `backend/app/api/health.py` |
## 22.7 关键代码理解
> `/health` 只证明应用进程能响应；`/health/readiness` 还检查关键依赖与受保护部署约束，因此更适合作为接流量门槛。
## 22.8 最小动手运行
```bash
docker compose config
pytest backend/tests/test_health.py -q
```
## 22.9 故障注入实验
> 临时提供无效数据库路径，比较 health 与 readiness 的响应差异，然后恢复配置。
## 22.10 调试路径与常见误判
> 依次检查容器状态、后端日志、readiness、Nginx 上游和浏览器请求，不要只凭首页能打开判断后端健康。
## 22.11 独立编码练习
> 写一份部署前检查清单，覆盖密钥、数据库、认证、端口与 readiness。
## 22.12 测试或评测验证
> 验证 Compose 配置可解析、前端构建通过、健康测试通过且密钥不进入镜像或日志。
## 22.13 面试复述题
> liveness 和 readiness 在这个项目中分别证明什么？
## 22.14 掌握度检查与下一章
> 能从浏览器一路定位到容器依赖。下一部分进入测试与真实模型评测。
