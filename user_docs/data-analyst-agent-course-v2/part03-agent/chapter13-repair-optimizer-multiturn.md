# 第13章 SQL Repair、优化与多轮上下文

> 本章预计 2 小时，理解执行失败恢复、只读优化建议和安全会话继承。练习均可使用 Fake LLM 与临时 SQLite/DuckDB。

## 13.1 学习目标

> 能解释错误分类、差异化 Repair、重新校验、规则化 Optimizer、EXPLAIN、安全会话摘要、失败轮最小记录和澄清恢复。

## 13.2 前置知识

> 需要完成第12章状态机，并理解 SQL Guard 与执行错误不是同一阶段。

## 13.3 为什么需要这一模块

> 模型 SQL 可能因字段、表、方言、类型或聚合错误而执行失败；用户也会用“只看前三名”等省略式追问。恢复能力必须保留原意和安全边界，不能把危险或越权请求改写成可执行查询。

## 13.4 输入、输出与依赖

| 模块 | 输入 | 输出 |
|---|---|---|
| Repair | 原 SQL、诊断错误、Schema、错误类型 | repaired_sql、分类原因 |
| Optimizer | 已安全执行 SQL、结果 | 去重建议列表 |
| SessionStore | session_id、final state | 最近3轮精简上下文 |
| Clarification store | 原问题、稳定候选 | resolved question 或 expired |

## 13.5 执行流程

```text
safe SQL execution error → classify → repair LLM
  → SQL Guard → Permission → execute

successful execution → optimize → answer → safe summary
safe execution failure → minimal failed summary
intent/SQL/permission block → do not append context
```

## 13.6 当前代码地图

| 内容 | 路径 |
|---|---|
| 错误分类 | `backend/app/security/error_classifier.py` |
| Repair | `backend/app/agents/sql_repair.py` |
| Optimizer | `backend/app/agents/sql_optimizer.py` |
| 上下文 | `backend/app/agents/conversation_context.py` |
| Session | `backend/app/agents/session_store.py` |

## 13.7 关键代码理解

### 13.7.1 Repair 分类与策略

> 当前分类覆盖列/表/函数不存在、类型不匹配、聚合误用、语法、列歧义、超时等；不同类别使用更具体的 Prompt 后缀与低 temperature。错误分类影响修复提示，不授权 SQL。

### 13.7.2 三种重试不能混淆

> HTTP 重试处理网络/限流；SQL Repair 处理已通过 Guard 但数据库执行失败的 SQL；用户重新提问是新业务请求。它们的预算、审计和安全语义不同。

### 13.7.3 Optimizer 只处理成功结果

> 先检查 `SELECT *` 和 row_count 上限；没有明显建议时，才把 `EXPLAIN SQL` 再送入 SQL Guard，并通过 QueryRunner 获取计划。执行失败的 SQL不会为了“优化”再次运行。

### 13.7.4 会话到底保存什么

> 成功轮保存问题、安全 SQL、列名、行数、截断答案和建议，不保存 rows。已通过 Intent/SQL/Permission 但执行失败的轮次保存问题、SQL 和截断错误，帮助后续换问法；危险意图、SQL Guard 阻断和权限拒绝不进入上下文。
>
> SessionStore 使用 SQLite、每线程连接与 WAL，默认保留最近3轮。失败轮并非一概丢弃，这是当前源码与早期文档容易混淆的地方。

## 13.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
pytest backend/tests/test_sql_repair.py backend/tests/test_sql_optimizer.py backend/tests/test_session_store.py backend/tests/test_conversation_context.py -q
```

## 13.9 故障注入实验

> 用错误列触发执行失败，Fake Repair 返回正确列，观察重新 Guard/Permission。再构造 permission_allowed=false 的 final state，确认 SessionStore 不产生上下文；临时数据库实验后调用 clear/close。

## 13.10 调试路径与常见误判

> Repair 不触发时先确认 SQL 是否已通过 Guard、权限是否允许、执行是否失败、retry_count 是否小于上限。上下文异常时检查 session_id、最近轮次、安全标志和数据库文件，不要假设所有失败轮都被丢弃。

## 13.11 独立编码练习

> 为“按地区拆一下，只看前三名”设计最小上下文摘要，禁止完整 rows。再为 COLUMN_NOT_FOUND 写 Fake Repair 用例，断言修复后仍经过 validate 与 authorize。

## 13.12 测试或评测验证

> 验证每个错误类别、危险修复阻断、权限拒绝不入库、失败执行最小摘要、max_turns 截断、Session 隔离、EXPLAIN 再校验和建议去重。

## 13.13 面试复述题

> 1. 为什么危险 SQL 和权限拒绝不能进入 Repair？
>
> 2. 当前项目是否保存失败轮？保存哪些、不保存哪些？
>
> 3. 为什么 Optimizer 的 EXPLAIN 还要经过 Guard？

## 13.14 掌握度检查与下一章

> 能区分三种重试；准确描述 Session 保存边界；画出 Repair 回流。下一部分建立安全、权限与可靠性。
