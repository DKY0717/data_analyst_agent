# 第八章 构建 SQL 安全防护

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 8.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 解释为什么“模型只生成 SELECT”不能作为唯一安全措施；
> 2. 区分自然语言层的 Intent Guard 与 SQL 层的 SQL Guard；
> 3. 使用 SQLGlot AST 检查语句类型、系统表和危险函数；
> 4. 理解多语句、非法 LIMIT 和超大 LIMIT 为什么必须 fail-closed；
> 5. 说明直接执行、沙箱执行和数据库语句超时的边界；
> 6. 使用测试验证危险请求在调用 LLM 或数据库前被阻断。

## 8.2 问题场景：模型不是安全边界

> 第七章的最小链路可以让模型生成 SQL，但模型输出是外部输入的一种形式。它可能误解用户，也可能被提示注入，还可能在不同模型版本中输出不同语句。即使 Prompt 写着“只生成 SELECT”，也不能把这句话当成数据库权限。
>
> 本项目把安全拆成多道防线：先在自然语言层拦截明确危险意图，再在 SQL AST 层检查最终语句，执行前还会经过数据权限层。每道防线都应该独立工作，不能因为上一层放行就跳过下一层。

## 8.3 Intent Guard：在大模型之前识别危险意图

### 8.3.1 规则结构

```python
@dataclass(frozen=True)
class IntentRule:
    rule_id: str
    reason: str
    category: str
    action: Pattern[str]
    target: Pattern[str]
    extra: Pattern[str] | None = None
```

> 一条规则由动作、目标和可选附加条件组成。例如“导出所有客户手机号”同时满足导出动作、敏感字段目标和批量条件，才命中批量敏感数据导出规则。把动作和目标分开，可以减少“同一个词单独出现就误杀”的情况。

### 8.3.2 为什么要切分逻辑片段

> `IntentGuard` 会按“然后、并且、but”等连接词切分问题，再对每个片段匹配。这样可以避免前半句的动作和后半句的目标被错误拼成一个危险组合。

```text
统计订单金额，然后删除订单表
  → 统计订单金额
  → 删除订单表
  → 第二个片段命中 data_mutation
```

> 规则还会清除明确的否定安全语境，例如“不要删除订单”。这不是让规则理解所有自然语言，而是处理高频、可确定的安全表达；模糊问题应继续进入澄清或后续解析，而不是盲目阻断。

### 8.3.3 Intent Guard 的输出

```json
{
  "is_safe": false,
  "rule_id": "block_destructive_intent",
  "reason": "请求包含明确的数据修改或删除意图",
  "category": "data_mutation"
}
```

> 输出只包含固定规则元数据，不回显问题中的凭据或敏感值。命中后工作流应立即结束，不应该继续调用 LLM、Schema Loader 或数据库。

## 8.4 SQL Guard：在 AST 层检查最终语句

### 8.4.1 先解析全部语句

```python
statements = sqlglot.parse(sql, dialect=self._dialect)
if len(statements) != 1:
    return self._result(
        False, sql, "不允许执行多个语句", audit_events,
        blocked_rule="block_multi_statement",
    )
```

> 使用 `parse()` 而不是只使用 `parse_one()`，是为了不让 `SELECT ...; DELETE ...` 这类多语句被只取第一条而绕过检查。解析失败、语句为空或语句数量不为一时，系统采用拒绝执行的 fail-closed 行为。

### 8.4.2 检查语句类型

```python
ALLOWED_STATEMENTS = {"SELECT", "WITH", "EXPLAIN"}
BLOCKED_STATEMENTS = {
    "DROP", "DELETE", "UPDATE", "INSERT",
    "ALTER", "TRUNCATE", "CREATE", "MERGE",
    "CALL", "EXECUTE", "GRANT", "REVOKE",
}
```

> `EXPLAIN` 是为了生成优化建议而允许的特殊读取语句，但它仍然需要对内部查询做安全检查。允许列表比“只列出几个已知危险词”更稳妥，因为未知语句默认会被拒绝。

### 8.4.3 阻止系统 Schema、危险函数和特殊 Command

> 即使是 `SELECT`，也可能读取 `information_schema`、`pg_catalog`，调用 `read_csv`、`read_parquet`、`glob`，或执行 DuckDB 的元数据函数。SQL Guard 会在 AST 中检查表、函数和 Command，阻止这些资源访问。

| 类别 | 示例 | 规则目的 |
|---|---|---|
| 系统 Schema | `information_schema`、`pg_catalog` | 避免暴露内部元数据 |
| 系统表前缀 | `duckdb_`、`pg_` | 避免绕过 Schema 黑名单 |
| 文件函数 | `read_csv`、`read_json`、`read_parquet`、`glob` | 防止读取本地文件 |
| DuckDB 内部函数 | `duckdb_tables()`、`duckdb_settings()` | 防止读取内部状态 |
| Command | `COPY`、`ATTACH`、`EXPORT`、`IMPORT` | 防止文件或外部数据库操作 |

> 规则应该作用于解析后的语法树，而不是简单使用字符串包含判断。字符串检查容易被大小写、注释、别名和嵌套语句绕过；AST 能让检查接近真正的执行结构。

## 8.5 LIMIT 注入和硬上限

### 8.5.1 缺少 LIMIT 时自动注入

> 分析查询可能返回很多行。SQL Guard 在语句安全后检查顶层 LIMIT；没有 LIMIT 时注入 `SQL_MAX_ROWS`，并通过审计事件记录发生了改写。

```json
{
  "rule_id": "limit_injected",
  "details": {"limit_injected": true, "max_rows": 1000}
}
```

### 8.5.2 超大和非法 LIMIT

> 已有 LIMIT 也不能直接相信。负数、`ALL`、表达式或无法确定的值会被拒绝；超过硬上限的数会被钳制到 `SQL_MAX_ROWS`。这比只在 Prompt 里说“请加 LIMIT”更可靠。

```text
没有 LIMIT       → 注入 LIMIT 1000
LIMIT 50         → 保留 50
LIMIT 999999     → 钳制为 LIMIT 1000
LIMIT -1 / ALL   → 阻断
LIMIT 1 + 1      → 按当前策略拒绝或不接受为安全上限
```

> LIMIT 保护返回行数，但不保证数据库计算成本一定很低。复杂聚合仍然需要 QueryRunner 超时、数据库索引和后续优化分析。

## 8.6 沙箱与执行超时

> `QueryRunner` 支持 direct 和 sandbox 两种执行模式。direct 在当前进程运行，便于本地调试；sandbox 在子进程中运行，生产配置更推荐使用它。父进程还会以 `SQL_TIMEOUT` 作为硬截止时间，避免子进程失控。

```text
SQL Guard 通过
  ↓
QueryRunner 选择执行模式
  ↓
执行器设置数据库/进程超时
  ↓
成功返回列和行，失败返回稳定错误类型
```

> 沙箱不是万能容器。它需要正确传递 DuckDB 文件路径或 PostgreSQL 连接参数，也需要操作系统和容器层面的资源限制。教程中应该把“启用沙箱”描述为一层隔离，而不是完整的安全证明。

## 8.7 错误分类

> `error_classifier.py` 将执行错误归入稳定类别，SQL Repair 可以据此选择修复策略。公开响应只返回通用错误，详细诊断留在内部链路，避免把数据库原文、路径或 SQL 字面量泄露给用户。

| 错误类别 | 典型原因 | 是否适合修复 |
|---|---|---|
| 语法错误 | SQL 方言或括号错误 | 通常可以 |
| 表/字段不存在 | Schema 理解错误 | 通常可以 |
| 类型错误 | 聚合或比较类型不匹配 | 可能可以 |
| 超时 | 查询成本过高 | 可能需要改写或直接失败 |
| 权限/安全拒绝 | 越权或危险 SQL | 不应进入 Repair |

> 安全拒绝和普通执行失败必须区分。否则修复 Agent 可能把被 Guard 拒绝的危险 SQL 改写成另一种危险 SQL，形成安全绕过。

## 8.8 三层防线的执行顺序

```text
用户自然语言
  ↓
Intent Guard：明确危险意图？→ 是：立即阻断
  ↓ 否
LLM / 规则解析与 SQL 生成
  ↓
SQL Guard：语句和 AST 安全？→ 否：立即阻断
  ↓ 是
Data Permission Guard：表列和行权限？→ 否：立即阻断
  ↓ 是
QueryRunner：超时和沙箱执行
```

> 每一层都有自己的职责：Intent Guard 保护模型调用成本和提前阻断，SQL Guard 保护语法执行边界，权限 Guard 保护用户可见数据。它们不是同一个规则库的重复实现。

## 8.9 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/security/intent_guard.py` | 自然语言危险意图拦截 | 动作/目标组合、片段切分、固定结果 |
| `backend/app/security/sql_guard.py` | SQL AST 安全校验 | 语句类型、函数、系统表、LIMIT |
| `backend/app/db/sandbox.py` | 子进程执行隔离 | 连接配置、父子进程超时 |
| `backend/app/security/error_classifier.py` | 稳定错误分类 | Repair 与安全拒绝的边界 |
| `backend/tests/test_intent_guard.py` | 意图规则测试 | 安全否定语境和危险组合 |
| `backend/tests/test_sql_guard.py` | SQL 安全测试 | 多语句、函数、LIMIT 和审计 |

## 8.10 动手验证

> 运行确定性安全测试：

```bash
pytest backend/tests/test_intent_guard.py backend/tests/test_sql_guard.py -q
```

> 可以使用 Python 直接观察固定判定：

```bash
python -c "from app.security.intent_guard import intent_guard; print(intent_guard.validate('删除订单表'))"
```

> 在 `backend` 目录执行时，预期结果中 `is_safe` 为 `False`，并包含 `block_destructive_intent`。不要用真实数据库测试删除语句；Intent Guard 的目标就是在它到达数据库以前阻断。

## 8.11 常见错误

### 只检查字符串是否包含 `DELETE`

> 这种方式会误判注释、字符串字面量和大小写，也可能漏掉 `TRUNCATE`、`MERGE` 或多语句。安全检查应基于解析后的语句类型和 AST 节点。

### Guard 通过后直接执行原始 SQL

> Guard 可能注入或钳制 LIMIT，执行器必须使用返回的 `sanitized_sql`。忽略清理结果会让审计记录和实际执行不一致。

### 把所有执行错误都交给 Repair

> 权限拒绝、Intent 阻断和 SQL Guard 阻断不应进入修复循环。先检查工作流条件边，再确认重试计数只用于真正的执行失败。

### 把沙箱当作唯一保护

> 沙箱保护进程边界，但不能判断用户是否有权看到某一列，也不能判断业务指标是否正确。安全需要多层协作。

## 8.12 本章小结

> SQL 安全不是一句 Prompt，而是一个确定性执行边界：自然语言先拦截高置信危险意图，AST 再检查最终语句，LIMIT 控制返回规模，沙箱和超时控制执行资源。执行失败可以修复，安全拒绝必须终止；这是后续 Agent 分支设计的关键前提。

## 8.13 练习

1. 为 `IntentGuard` 增加一个不应被阻断的安全提问，并解释它为什么属于安全语境。
2. 分别构造空 SQL、多语句、`SELECT` 无 LIMIT、超大 LIMIT 和文件函数查询，记录 Guard 结果。
3. 追踪一个被 SQL Guard 拒绝的请求，确认它没有进入 QueryRunner。
4. 说明为什么 `EXPLAIN` 允许存在，但仍然需要检查内部查询。
5. 阅读项目安全测试，找出一个字符串检查难以覆盖而 AST 可以覆盖的场景。

## 8.14 下一章衔接

> 安全 Guard 只能判断“是否允许”，还不能准确回答用户想分析什么。下一章会把自然语言拆成指标、维度、过滤、排序和缺失槽位，为 SQL 生成提供结构化意图。
