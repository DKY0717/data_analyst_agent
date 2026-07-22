# 第17章 重试、错误分类与失败隔离

> 本章预计 2 小时，学习按照已完成阶段选择重试、Repair、降级或终止。实验使用异常替身。

## 17.1 学习目标

> 能区分 HTTP attempt、LLM logical call、SQL Repair、用户重提；能分类超时/429/4xx/5xx/空 content/SQL错误/答案失败/安全阻断。

## 17.2 前置知识

> 需要理解统一 LLM 客户端、Graph 条件边、QueryRunner 和审计事件。

## 17.3 为什么需要这一模块

> 无差别重试会放大费用与尾延迟，也可能让模型改写危险或越权意图。失败隔离要先判断哪一步已形成可信产物，再决定保留什么、是否可重复调用外部依赖。

## 17.4 输入、输出与依赖

| 失败 | 处理 | 保留证据 |
|---|---|---|
| 网络/部分限流或服务错误 | 有界 HTTP retry | attempt_count、错误类型 |
| 无效 LLM content/JSON | LLMError | stage、调用指标 |
| 安全 SQL 执行错误 | 有预算时 Repair | 原 SQL、分类、retry_count |
| Intent/SQL/Permission 阻断 | 立即终止 | rule_id、事件 |
| SQL 已成功、答案失败 | degraded answer | SQL、columns、rows、answer_error |

## 17.5 执行流程

```text
exception/result → classify by stage
  ├─ retry same HTTP call
  ├─ repair SQL then re-guard
  ├─ degrade presentation, keep data
  └─ stop fail-closed
```

## 17.6 当前代码地图

| 内容 | 路径 |
|---|---|
| LLM transport | `backend/app/services/llm_service.py` |
| Exception types | `backend/app/utils/exceptions.py` |
| SQL classifier | `backend/app/security/error_classifier.py` |
| Graph isolation | `backend/app/agents/graph.py` |
| Cache boundary | `backend/app/api/query.py` |

## 17.7 关键代码理解

### 17.7.1 provider 错误必须脱敏

> `LLMResponseError` 只保留清洗后的 HTTP status、provider code/type；供应商 message 可能回显输入，不能传播到 API、Artifact 或日志。认证失败与请求拒绝通常不应靠重复请求解决。

### 17.7.2 空 content 不是空答案

> reasoning 有值但 content 为空时，结构化任务没有可消费输出，应形成明确失败。MiMo 真实评测说明反复等待此类响应会放大尾延迟，但不代表 SQL Repair 本身失败。

### 17.7.3 答案失败后的部分成功

> 若 SQL 已安全执行，AnswerGenerator 失败时 Graph 生成安全降级说明，保留 SQL 和结构化结果，并写 `answer_error/degraded` 事件。降级结果不进入共享查询缓存，防止临时供应商故障长期污染。

### 17.7.4 禁止 Repair 的失败

> 危险意图、SQL Guard 阻断、权限拒绝都不是可修复数据库错误；Repair 只能接已通过安全和授权、但执行失败的 SQL。

## 17.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
pytest backend/tests/test_llm_service.py backend/tests/test_agent_graph.py backend/tests/test_answer_generator.py -q
```

## 17.9 故障注入实验

> Fake AnswerGenerator 抛出 LLMError，断言 execution_success、SQL、columns/rows 保留，answer_error 存在且缓存不写；再让 SQL Guard 拒绝，断言 Repair 调用数为0。

## 17.10 调试路径与常见误判

> 记录 stage、logical call、attempt_count、retry_count、execution_success 与最终 status。三次 HTTP 尝试可能仍是一轮 SQL 生成；Agent retry_count 只表示 SQL Repair。不能只看总耗时就判定数据库慢。

## 17.11 独立编码练习

> 为 DNS、401、429、空 content、未知列、权限拒绝、答案失败写分类表，标注：是否重试、是否 Repair、是否降级、保留字段和用户提示。

## 17.12 测试或评测验证

> 覆盖 retry 后成功、不可重试4xx、空 content、异常脱敏、危险阻断不 Repair、权限拒绝不 Repair、重试耗尽、答案降级与缓存保护。

## 17.13 面试复述题

> 1. 失败隔离为什么比捕获所有异常更难？
>
> 2. HTTP attempt 与 SQL Repair 如何分别计数？
>
> 3. 为什么答案失败不应清空查询结果？

## 17.14 掌握度检查与下一章

> 能为每类故障选择唯一主路径；能准确说出部分成功边界；能解释 MiMo 空 content 的证据。下一章学习审计和观测。
