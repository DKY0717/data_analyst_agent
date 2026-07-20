# 学习过程故障排查

> 排查原则是先确认环境和边界，再修改业务代码。不要因为外部模型、端口或工作目录错误而关闭安全机制。

## 1. Python 无法导入 `app`

> 常见原因是命令运行目录错误或 `PYTHONPATH` 不包含 `backend`。先确认当前位置，再使用项目文档给出的根目录命令。

```powershell
Get-Location
pytest backend/tests/test_health.py -q
```

## 2. 数据库没有业务表

> 先确认数据库配置和种子脚本，不要直接修改 Schema Loader。DuckDB 演示库通过固定脚本重建，PostgreSQL 才使用 Alembic。

```powershell
python database/seed_data.py
pytest backend/tests/test_seed_data.py -q
```

## 3. 后端端口被占用

> 端口冲突属于进程环境问题。确认占用进程和启动参数后，再决定停止旧进程或更换端口。

```powershell
netstat -ano | Select-String ':8000'
```

## 4. LLM 返回 401、429、超时或空内容

> 401 通常与凭据或端点有关，429 通常与配额或限流有关，超时和空 content 可能来自供应商长尾行为。日志只保留脱敏类型和状态，不要把 API Key 或完整响应复制到学习笔记。
>
> 没有真实模型时，优先运行 `backend/tests/test_llm_service.py` 和确定性核心路径，不要伪造真实通过结果。

## 5. 前端能打开但没有 Schema

> 先检查后端 readiness、Vite 代理和浏览器网络请求。页面加载成功只能证明静态资源可用，不能证明 API 与数据库可用。

## 6. Docker readiness 失败

> 区分 demo 与 secure profile。secure 配置缺少强 Secret、认证或数据库条件时应 fail closed，不能通过降低安全配置来制造绿色状态。

## 7. GitHub Actions 红色

> 先区分普通 CI、真实模型分片和严格质量门禁。查看失败 job、步骤、日志和 artifact；缺失真实报告应标记为未验证，而不是自动归零或自动通过。
