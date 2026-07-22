# 第14章 Intent Guard 与 SQL Guard

> 本章预计 2 小时，学习模型前后的两层确定性安全边界。全部实验使用固定字符串，不调用真实模型或数据库。

## 14.1 学习目标

> 能区分危险自然语言、危险 SQL 类型和 SELECT 形式的数据外泄；能解释单语句、AST、系统对象、危险函数、EXPLAIN 与 LIMIT 规则；理解 fail closed。

## 14.2 前置知识

> 需要理解 SQL AST、完整图路由和为什么 LLM 输出不可信。

## 14.3 为什么需要这一模块

> Intent Guard 在任何 LLM、Schema 或数据库访问前阻断明显危险目的，减少费用和攻击面；SQL Guard 对实际生成物做独立验证，因为安全问题也可能来自模型误生成、Prompt 注入或 Repair。
>
> 两层处理的对象不同，不能互相替代。自然语言看起来正常也可能生成危险 SQL；危险请求也可能被模型改写成表面安全但违背用户目的的查询。

## 14.4 输入、输出与依赖

| Guard | 输入 | 成功输出 | 阻断证据 |
|---|---|---|---|
| Intent | 原始 question | `is_safe=true` | rule_id、category、reason |
| SQL | SQL 字符串 | sanitized_sql、LIMIT 事件 | blocked_rule、reason、audit event |

> SQL Guard 使用当前数据库后端选择 DuckDB/PostgreSQL 方言，并通过 SQLGlot 解析全部语句。任何解析异常、空 SQL、多语句或未知类型都拒绝。

## 14.5 执行流程

```text
question → normalize fragments → deterministic Intent rules
  → LLM/Repair → parse all SQL statements
  → statement allowlist → AST object/function checks
  → LIMIT validation/injection/clamp → safe SQL
```

## 14.6 当前代码地图

| 内容 | 路径 |
|---|---|
| Intent 规则 | `backend/app/security/intent_guard.py` |
| SQL AST | `backend/app/security/sql_guard.py` |
| 图路由 | `backend/app/agents/graph.py` |
| Intent 测试 | `backend/tests/test_intent_guard.py` |
| SQL 测试 | `backend/tests/test_sql_guard.py` |

## 14.7 关键代码理解

### 14.7.1 Intent 规则要看语境片段

> Guard 清理并分段问题，优先识别绕过安全策略，再检查危险数据操作等规则。规则应保留 rule_id，便于审计与评测，而不是只返回模糊“不能回答”。

### 14.7.2 只允许一个语句

> `sqlglot.parse()` 解析全部语句，避免 `parse_one()` 只看到第一条 SELECT 而漏掉后续 DROP。允许顶层 SELECT、WITH 与受控 EXPLAIN；DDL/DML、COPY/ATTACH 等命令拒绝。

### 14.7.3 SELECT 也可能外泄

> Guard 遍历 Table 与 Func 节点，阻断 `information_schema`、`pg_catalog`、`duckdb_*`、`pg_*`，以及 `read_csv_auto`、`read_parquet`、`glob` 等读取文件/元数据函数。

### 14.7.4 EXPLAIN 不能绕过

> SQLGlot 对 DuckDB EXPLAIN 的解析形态特殊，Guard 会取出内部查询再次做 AST 安全检查。优化器因此不能借 EXPLAIN 访问被禁止对象。

### 14.7.5 解析失败即拒绝

> fail closed 表示无法证明安全就不执行。它可能降低某些奇特 SQL 的可用性，但不应为了“让模型成功”回退到字符串执行。

## 14.8 最小动手运行

> 工作目录：项目根目录。网络/数据库/真实模型：不需要。

```bash
pytest backend/tests/test_intent_guard.py backend/tests/test_sql_guard.py -q
```

## 14.9 故障注入实验

> 分别验证：“删除订单表”在 Intent 节点结束；正常问题但 Fake LLM 返回 `DROP TABLE orders` 在 SQL Guard 结束；`SELECT * FROM read_csv_auto(...)` 虽是 SELECT 仍被危险函数规则拒绝。

## 14.10 调试路径与常见误判

> 先确认阻断阶段和 rule_id，再检查规范化输入、方言、statement type、AST 表/函数节点。关键词搜索不能可靠区分字符串字面量、注释和真实语法；安全阻断是预期行为，不应计入普通 SQL 执行失败。

## 14.11 独立编码练习

> 为一个新危险 DuckDB 文件函数设计测试：直接调用、大小写变化、嵌套子查询、函数名出现在字符串中。只写预期与测试草案，不先修改规则。

## 14.12 测试或评测验证

> 检查空 SQL、多语句、WITH、EXPLAIN、系统表、文件函数、解析错误以及 LIMIT 边界。还要断言阻断时 Runner 和 Repair 未被调用。

## 14.13 面试复述题

> 1. 为什么有 Intent Guard 还需要 SQL Guard？
>
> 2. 为什么 SELECT-only 仍不安全？
>
> 3. fail closed 的代价和收益是什么？

## 14.14 掌握度检查与下一章

> 能为危险请求指出正确阻断层；能列出至少五类 SQL AST 风险；能解释 EXPLAIN 再校验。下一章学习资源隔离。
