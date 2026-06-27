# SQL 安全防护（Intent Guard + SQL Guard）

## 1. 学习目标

> - 理解为什么需要两层安全防护
> - 了解 Intent Guard 如何在 LLM 调用前拦截危险意图
> - 了解 SQL Guard 如何用 AST 解析校验 SQL 安全性
> - 理解自动 LIMIT 注入机制

## 2. 为什么需要两层防护

> 这个系统允许用户用自然语言提问，然后自动生成 SQL 并执行。这意味着：
>
> - 用户可能无意中问了危险的问题（"删除所有订单"）
> - LLM 可能生成不安全的 SQL（`DROP TABLE`）
> - LLM 可能生成查询系统表的 SQL（泄露数据库内部信息）
>
> 因此系统设计了**两层防护**：

```text
第一层：Intent Guard（意图守卫）
  - 在 LLM 调用之前执行
  - 基于正则表达式匹配危险意图
  - 零延迟，不消耗 API 调用

第二层：SQL Guard（SQL 守卫）
  - 在 SQL 执行之前执行
  - 基于 SQL AST 解析校验
  - 自动注入 LIMIT 防止大结果集
```

## 3. Intent Guard（意图守卫）

> 代码在 `backend/app/security/intent_guard.py`。

### 3.1 设计思想

> Intent Guard 的核心思想是：**在调用 LLM 和数据库之前，用确定性规则拦截明确危险的请求。**
>
> 它不依赖 LLM 判断，而是用正则表达式匹配"动作 + 目标"的组合。

### 3.2 规则定义

> 每条规则由**动作（action）**和**目标（target）**组成：

```python
@dataclass(frozen=True)
class IntentRule:
    rule_id: str           # 规则ID
    reason: str            # 阻断原因
    category: str          # 风险类别
    action: Pattern[str]   # 动作正则（删除、导出、查看...）
    target: Pattern[str]   # 目标正则（订单、密钥、系统文件...）

    def matches(self, question: str) -> bool:
        # 动作和目标必须同时匹配
        return bool(
            self.action.search(question)
            and self.target.search(question)
        )
```

> **为什么要"动作 + 目标"双重匹配？**
>
> 单独匹配动作（如"删除"）会误杀正常问题（"查询被删除的订单"）。
> 单独匹配目标（如"订单"）会阻断所有订单相关查询。
> 只有"动作 + 目标"同时出现才判定为危险。

### 3.3 四条安全规则

```python
_RULES = (
    # 规则 1：数据修改/删除意图
    IntentRule(
        rule_id="block_destructive_intent",
        category="data_mutation",
        action=匹配"删除/清空/销毁...订单表/数据库",
        target=匹配"订单表/支付记录/客户表/数据库",
    ),

    # 规则 2：凭据访问意图
    IntentRule(
        rule_id="block_credential_access_intent",
        category="credential_access",
        action=匹配"查看/显示/读取/导出...",
        target=匹配"api_key/token/密钥/密码...",
    ),

    # 规则 3：系统文件访问意图
    IntentRule(
        rule_id="block_system_access_intent",
        category="system_access",
        action=匹配"读取/查看/打开/访问...",
        target=匹配"/etc/passwd/系统文件/主机文件...",
    ),

    # 规则 4：批量敏感数据导出
    IntentRule(
        rule_id="block_sensitive_export_intent",
        category="sensitive_export",
        action=匹配"导出/下载/提取...",
        target=匹配"手机号/电话号码/身份证/邮箱...",
        extra=匹配"全部/所有/批量/完整",  # 需要额外的批量标记
    ),
)
```

### 3.4 安全上下文排除

> 有些问题虽然包含"删除"等关键词，但实际上是安全的讨论：

```python
_SAFE_ACTION_CONTEXT = 匹配:
  "不要删除订单表"      → 安全（是否定句）
  "能否删除订单表"      → 安全（是疑问句，不是执行请求）
  "被删除的订单"        → 安全（是被动语态，讨论已删除的数据）
```

> Intent Guard 会先移除这些安全上下文，再对剩余内容进行规则匹配。

### 3.5 验证流程

```python
def validate(self, question: str) -> dict:
    # 1. 按连接词拆分问题为多个片段
    #    "查询销售额最高的商品，然后删除订单表"
    #    → ["查询销售额最高的商品", "删除订单表"]
    fragments = self._clean_fragments(question)

    # 2. 每个片段独立匹配规则
    for fragment in fragments:
        for rule in self._RULES:
            if rule.matches(fragment):
                return {"is_safe": False, "rule_id": rule.rule_id, ...}

    # 3. 所有片段都安全，放行
    return {"is_safe": True, ...}
```

> **为什么要拆分片段？**
>
> 用户可能在一个问题中混合安全和危险的意图："查询销售额最高的商品，然后删除订单表"。如果整体匹配，"查询销售额"是安全的，可能会漏掉后面的"删除订单表"。

## 4. SQL Guard（SQL 守卫）

> 代码在 `backend/app/security/sql_guard.py`。
>
> 即使 Intent Guard 放行了，LLM 生成的 SQL 仍然可能不安全。SQL Guard 在 SQL 执行前做最后的校验。

### 4.1 为什么用 AST 解析

> 不能简单用字符串匹配来判断 SQL 是否安全。比如：
>
> - `SELECT * FROM orders WHERE status = 'DROP TABLE'` — 安全，字符串里的 "DROP TABLE" 不是命令
> - `SELECT * FROM customers; DROP TABLE orders` — 危险，多语句注入
>
> SQLGlot 会把 SQL 解析成**抽象语法树（AST）**，可以精确识别语句类型、表名、函数名，不会被字符串字面量迷惑。

### 4.2 校验流程

```python
def validate(self, sql: str) -> Dict[str, Any]:
    # 1. 空 SQL 检查
    if not sql or not sql.strip():
        return {"is_safe": False, "reason": "SQL 为空"}

    # 2. 多语句检查
    statements = sqlglot.parse(sql, dialect="duckdb")
    if len(statements) != 1:
        return {"is_safe": False, "reason": "不允许执行多个语句"}

    # 3. 语句类型检查
    statement_type = self._get_statement_type(parsed)
    if statement_type not in {"SELECT", "WITH", "EXPLAIN"}:
        return {"is_safe": False, "reason": f"禁止的语句类型: {statement_type}"}

    # 4. AST 安全检查（系统表、危险函数）
    security_error = self._validate_ast_safety(parsed)
    if security_error:
        return {"is_safe": False, "reason": security_error}

    # 5. 清理 SQL（自动注入 LIMIT）
    sanitized_sql, limit_injected = self._sanitize_sql(parsed)

    return {"is_safe": True, "sanitized_sql": sanitized_sql}
```

### 4.3 语句类型白名单

```python
ALLOWED_STATEMENTS = {"SELECT", "WITH", "EXPLAIN"}

BLOCKED_STATEMENTS = {
    "DROP", "DELETE", "UPDATE", "INSERT",
    "ALTER", "TRUNCATE", "CREATE", "MERGE",
    "CALL", "EXECUTE", "GRANT", "REVOKE"
}
```

> 只允许查询语句，所有修改数据的语句都被拦截。

### 4.4 AST 安全检查

```python
def _validate_ast_safety(self, parsed):
    # 检查是否访问系统表
    for table in parsed.find_all(exp.Table):
        table_name = (table.name or "").lower()
        schema_name = (table.db or "").lower()

        if schema_name in {"information_schema", "pg_catalog"}:
            return "禁止访问系统表"

        if table_name.startswith(("duckdb_", "pg_")):
            return "禁止访问系统表"

    # 检查是否调用危险函数
    for func in parsed.find_all(exp.Func):
        function_name = (getattr(func, "name", "") or "").lower()
        if function_name in {"read_csv", "read_json", "glob", ...}:
            return f"禁止调用危险函数: {function_name}"

    return None  # 安全
```

> **为什么要拦截系统表和文件函数？**
>
> - `information_schema` 包含数据库元数据，可能泄露表结构信息
> - `read_csv`、`read_json` 等函数可以读取服务器上的文件，存在数据外泄风险
> - `duckdb_tables()` 等系统函数暴露内部信息

### 4.5 自动 LIMIT 注入

```python
def _sanitize_sql(self, parsed, statement_type):
    # 如果 SQL 没有 LIMIT 子句，自动加上
    if not parsed.args.get("limit"):
        parsed = parsed.limit(self.max_rows)  # 默认 1000
        limit_injected = True

    return parsed.sql(dialect="duckdb"), limit_injected
```

> **为什么自动加 LIMIT？**
>
> - 防止 LLM 生成 `SELECT * FROM orders` 这种返回百万行的查询
> - 保护数据库不会因为大结果集而耗尽内存
> - 保护网络带宽
> - `LIMIT 1000` 对于数据分析场景通常足够，用户需要更多时可以明确指定

## 5. 两层防护的协作

```text
用户: "删除所有订单"
  → Intent Guard: 匹配到"删除"+"订单" → 阻断，返回"请求包含明确的数据修改意图"
  → 不调用 LLM，不访问数据库

用户: "查询销售额最高的商品"
  → Intent Guard: 安全，放行
  → LLM 生成 SQL: SELECT product_name, SUM(quantity * unit_price) as sales ...
  → SQL Guard: 语句类型 SELECT ✓，无系统表 ✓，无危险函数 ✓
  → 自动注入 LIMIT 1000
  → 执行 SQL

用户: "查询所有客户的手机号，然后导出"
  → Intent Guard: 匹配到"导出"+"手机号"+"所有" → 阻断
  → 不调用 LLM

用户: "读取 /etc/passwd 文件"
  → Intent Guard: 匹配到"读取"+"/etc/passwd" → 阻断
```

## 6. 安全设计原则

| 原则 | 说明 |
|------|------|
| 默认拒绝 | 不在白名单内的都拒绝 |
| 失败关闭 | 任何异常都视为不安全 |
| 确定性优先 | 安全判断不依赖 LLM |
| 最小权限 | 只允许 SELECT，禁止一切修改操作 |
| 纵深防御 | Intent Guard + SQL Guard 双层防护 |
| 不泄露信息 | 错误信息不暴露 SQL、数据库结构或用户输入 |

## 7. 下一步

> 安全防护理解后，接下来学习：
>
> - **LLM 服务封装** — 了解系统如何调用大模型生成 SQL 和答案
