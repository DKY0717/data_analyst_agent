# 第15章 查询沙箱、LIMIT 与超时

> 本章预计 1～2 小时，学习安全 SQL 的资源边界。故障实验只能使用隔离测试数据库。

## 15.1 学习目标

> 能解释 LIMIT 注入/钳制/拒绝、结果上限、sandbox 子进程、超时终止、direct 与 sandbox 模式、双后端连接配置和诊断脱敏。

## 15.2 前置知识

> 需要完成第14章 SQL Guard，并理解进程、超时和数据库连接的基本概念。

## 15.3 为什么需要这一模块

> SELECT 可能全表扫描、生成巨量结果、读取复杂 JOIN 或长时间占用连接。语法安全不代表资源安全；应用主进程也不能被一个查询崩溃拖走。

## 15.4 输入、输出与依赖

> 输入必须是 Guard 产生的 sanitized SQL；QueryRunner 根据 `SANDBOX_MODE` 选择子进程或直接执行，输出 success、columns、rows、row_count、execution_time_ms、execution_mode 或结构化错误。

| 层 | 约束 |
|---|---|
| SQL Guard | 顶层 LIMIT 静态验证、注入与钳制 |
| SandboxExecutor | 子进程隔离、wall-clock timeout |
| PostgreSQL direct | 事务级 statement_timeout |
| QueryRunner | 统一成功/失败结构与诊断边界 |

## 15.5 执行流程

```text
validated SQL → QueryRunner
  ├─ sandbox → JSON stdin → worker process → JSON stdout / kill on timeout
  └─ direct  → DB session + backend timeout
→ structured result
```

## 15.6 当前代码地图

| 内容 | 路径 |
|---|---|
| LIMIT | `backend/app/security/sql_guard.py` |
| Runner | `backend/app/db/query_runner.py` |
| Sandbox | `backend/app/db/sandbox.py` |
| Worker | `backend/app/db/_sandbox_worker.py` |
| 测试 | `backend/tests/test_query_runner.py` |

## 15.7 关键代码理解

### 15.7.1 LIMIT 必须来自 AST

> 无顶层 LIMIT 时注入 `SQL_MAX_ROWS`；已有常量大于上限时钳制；负数、字符串或动态表达式拒绝。字符串里出现“LIMIT”不能欺骗 AST。

### 15.7.2 子进程协议

> 主进程把 SQL、connection_config、backend 和 timeout 编码为 JSON，通过 stdin 给固定 worker；worker stdout 返回 JSON。超时由 `subprocess.run(..., timeout=...)` 强制终止，崩溃不会直接击穿 FastAPI 进程。

### 15.7.3 双后端配置不同

> DuckDB worker 接受文件路径；PostgreSQL 接受 host/port/user/password/dbname。密码只在进程输入中传递，不可写入错误响应或日志。

### 15.7.4 诊断与用户错误分离

> 内部可选 `diagnostic_error` 供 Repair 分类，用户只看到“查询执行失败”。SandboxError、TimeoutError 与数据库异常应有不同 error_type。

## 15.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要；测试使用临时数据库与替身。

```bash
pytest backend/tests/test_query_runner.py backend/tests/test_sql_guard.py backend/tests/test_sandbox.py -q
```

## 15.9 故障注入实验

> 在临时 DuckDB 或 Fake worker 中构造超过极短 timeout 的查询，确认返回 TimeoutError 且主测试进程继续；再运行一个小 SELECT 恢复。不得在业务库制造高负载。

## 15.10 调试路径与常见误判

> 区分四种超时：LLM HTTP timeout、数据库 statement timeout、sandbox 进程 timeout、GitHub 评测 step timeout。记录 error_type、stage 和 elapsed；仅看到“75分钟超时”不能归因于 DuckDB。

## 15.11 独立编码练习

> 设计 `MiniExecutionResult`，包含 success、columns、rows、row_count、elapsed、mode、error_type 与公开 error；说明哪些诊断字段不能返回前端。

## 15.12 测试或评测验证

> 覆盖无 LIMIT、正常 LIMIT、超大 LIMIT、动态 LIMIT、字面量含 LIMIT、worker 非零退出、非法 stdout、timeout 和后续查询可恢复。

## 15.13 面试复述题

> 1. 为什么 SELECT-only 仍不足以保护数据库？
>
> 2. LIMIT、超时和子进程隔离分别防什么？
>
> 3. Sandbox 是否等于操作系统级完全隔离？

## 15.14 掌握度检查与下一章

> 能解释三层资源约束与四种超时；能追踪 worker 协议；不会把 sandbox 夸大为完整容器隔离。下一章进入认证和数据权限。
