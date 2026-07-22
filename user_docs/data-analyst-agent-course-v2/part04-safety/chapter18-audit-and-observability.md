# 第18章 安全审计与 LLM 可观测性

> 本章预计 1～2 小时，学习如何在不泄密的前提下证明系统做过什么。测试不调用真实模型。

## 18.1 学习目标

> 能解释 AuditEvent、请求级 AuditReport、权限摘要、LLM call/attempt/Token/耗时/成本、ContextVar 并发隔离和安全报告边界。

## 18.2 前置知识

> 需要理解完整 Agent、安全阻断、权限改写、Repair 和失败隔离。

## 18.3 为什么需要这一模块

> 没有结构化证据时，无法回答请求在哪个节点结束、为什么被阻断、是否注入 LIMIT、是否改写权限 SQL、调用模型几次、延迟来自哪里。日志字符串也不适合稳定 API 与离线评测。

## 18.4 输入、输出与依赖

| 输入 | 汇总输出 |
|---|---|
| 节点 audit events | blocked_rules、limit_injected、event timeline |
| auth_user 摘要 | user_id、roles、auth_method |
| authorization events | 表列、row filters、SQL changed |
| LLM calls | call_count、tokens、latency、attempts、optional cost |

> AuditReport 还包含 final_sql、is_sql_safe、execution_success 和 retry_count。它是当前请求证据，不是不可篡改合规账本。

## 18.5 执行流程

```text
start_trace → each node/LLM records structured event
  → Graph final state → AuditReportBuilder
  → API panel / evaluation report / incident analysis
```

## 18.6 当前代码地图

| 内容 | 路径 |
|---|---|
| Audit builder | `backend/app/agents/audit.py` |
| LLM observability | `backend/app/services/llm_observability.py` |
| Tracing | `backend/app/services/tracing.py` |
| API models | `backend/app/models/schemas.py` |
| 前端面板 | `frontend/src/components/AuditPanel.vue` |

## 18.7 关键代码理解

### 18.7.1 事件与摘要同时保留

> 事件保留 stage/action/status/message/rule_id/details 的时间顺序；摘要对 blocked_rules 去重，并以最后一次 authorization 事件表示最终权限决定。多次 Repair 的过程仍可从 events 检查。

### 18.7.2 ContextVar 隔离并发请求

> `_llm_calls` 使用 ContextVar；start_trace 为请求创建新列表；record/get 都深拷贝，避免异步请求或调用方原地修改共享指标。它解决请求上下文隔离，不等于持久化监控数据库。

### 18.7.3 成本未知必须是未知

> 只有 input/output 单价都配置且所有调用都有成本时，cost_available 才为 true；否则 estimated_cost 为 null。零调用或缺少价格不能伪造为零成本。

### 18.7.4 隐私最小化

> 允许记录模型名、Token、耗时、尝试数、SQL 元数据摘要和规则；禁止 API Key、Authorization、完整 Prompt、完整供应商响应和原始结果行。是否记录完整 SQL还要结合部署的数据分类要求。

## 18.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
pytest backend/tests/test_audit_report.py backend/tests/test_llm_observability.py -q
```

## 18.9 故障注入实验

> 并发启动两个异步 Fake LLM 轨迹，让它们使用不同 stage/token，断言互不串线；再触发 Intent 阻断，确认无 LLM call、blocked_rules 与事件顺序正确。

## 18.10 调试路径与常见误判

> 模型慢看 call latency/attempt；数据库慢看 execution_time；Repair 多看 retry_count；权限阻断看最后 authorization event。总耗时不等于各段简单相加；并发和外层等待需结合 tracing。

## 18.11 独立编码练习

> 设计一个不含 rows、Prompt、凭据的执行摘要：request_id、stage timings、SQL hash、tables、row_count、error_type。说明每个字段的调试价值和泄露风险。

## 18.12 测试或评测验证

> 验证并发隔离、深拷贝、Token 汇总、attempt 汇总、成本可用/不可用、阻断规则去重、最终权限事件和脱敏字段缺失。

## 18.13 面试复述题

> 1. 可观测性如何区分模型慢、数据库慢与 Repair 多？
>
> 2. ContextVar 解决什么、不解决什么？
>
> 3. 为什么未知成本不能写成0？

## 18.14 掌握度检查与下一章

> 能用一份 AuditReport 重建请求路径；能列出允许/禁止字段；能解释证据边界。下一部分学习产品 API 与前端。
