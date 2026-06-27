# SQL 生成、修复与优化

## 1. 学习目标

> - 了解 SQL 生成器如何利用 Schema 和意图信息生成 SQL
> - 理解 SQL 修复器如何根据错误信息修复 SQL
> - 了解 SQL 优化器如何生成优化建议

## 2. SQL 生成器

> 代码在 `backend/app/agents/sql_generator.py`。
>
> SQL 生成器是系统中最核心的组件，它把用户问题转换为可执行的 SQL。

### 2.1 输入信息

> 生成 SQL 需要以下信息：

| 信息 | 来源 | 作用 |
|------|------|------|
| 用户问题 | 用户输入 | 理解用户想查什么 |
| Schema 信息 | Schema Loader | 知道有哪些表和列 |
| 意图解析结果 | 意图解析系统 | 知道指标、维度、过滤条件 |
| 多轮对话上下文 | Session Store | 理解追问的上下文 |

### 2.2 Prompt 设计

```python
system_prompt = """你是一个专业的 SQL 生成助手。

要求：
1. 只生成 SELECT 或 WITH 查询语句
2. 使用 DuckDB 方言
3. 优先遵循业务语义层中的业务指标口径、维度定义
4. 如果用户是多轮追问，优先继承上下文中的分析意图
5. 返回严格的 JSON 格式

输出格式：
{
    "sql": "生成的 SQL 查询语句",
    "tables": ["使用的表名列表"],
    "explanation": "SQL 逻辑的简要说明"
}"""
```

> **关键设计：** prompt 中注入了 Schema 信息和意图解析结果，让 LLM 有足够上下文生成准确的 SQL。

### 2.3 生成流程

```python
async def generate(self, question, schema_context, conversation_context, analysis_intent):
    # 1. 构建 prompt
    user_prompt = f"""
数据库 Schema 与业务语义信息：
{schema_context}

{analysis_intent}

用户问题：{question}
请根据以上信息生成 SQL 查询。"""

    # 2. 调用 LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    content = await llm_client._call_api(messages, SQL_TEMPERATURE)

    # 3. 解析 JSON 响应
    return self._parse_response(content)
```

### 2.4 DuckDB 方言注意事项

> LLM 可能生成 MySQL 或 PostgreSQL 语法的 SQL，需要在 prompt 中强调 DuckDB 方言：
>
> - `LIMIT offset, count` → DuckDB 不支持，用 `LIMIT count OFFSET offset`
> - `DATE_FORMAT` → DuckDB 用 `STRFTIME`
> - `IFNULL` → DuckDB 用 `COALESCE`
> - `EXTRACT(QUARTER FROM date)` → DuckDB 支持，但 `strftime('%q')` 不支持

## 3. SQL 修复器

> 代码在 `backend/app/agents/sql_repair.py`。
>
> 当 SQL 执行失败时，修复器会分析错误原因并生成修复后的 SQL。

### 3.1 修复流程

```text
SQL 执行失败
  → 获取错误信息（如 "Catalog Error: Function date_format does not exist"）
  → 将原始 SQL + 错误信息 + Schema 发给 LLM
  → LLM 分析错误原因并生成修复后的 SQL
  → 返回修复后的 SQL 和修复原因
```

### 3.2 常见修复场景

| 错误类型 | 原因 | 修复方式 |
|----------|------|----------|
| 函数不存在 | 使用了 MySQL 函数 | 替换为 DuckDB 等效函数 |
| 列名不存在 | 拼写错误或用了别名 | 修正为正确的列名 |
| 语法错误 | SQL 方言差异 | 调整为 DuckDB 语法 |
| 类型不匹配 | 字符串和数字混用 | 添加 CAST 转换 |
| 表名不存在 | 用了错误的表名 | 修正为正确的表名 |

### 3.3 修复约束

> 修复器有严格约束：
> 1. **不能改变查询意图** — 只修复语法，不改变业务逻辑
> 2. **只生成 SELECT/WITH** — 不能生成 DDL/DML
> 3. **使用 DuckDB 方言** — 不能用其他数据库的语法
> 4. **修复后必须重新校验** — 防止修复出不安全的 SQL

## 4. SQL 优化器

> 代码在 `backend/app/agents/sql_optimizer.py`。
>
> SQL 执行成功后，优化器会分析 SQL 和执行结果，给出优化建议。

### 4.1 优化检查项

> 优化器会检查以下方面：

```python
def optimize(self, sql: str, query_result: dict) -> List[str]:
    suggestions = []

    # 1. 检查是否缺少索引建议
    # 2. 检查是否有全表扫描
    # 3. 检查结果集是否过大
    # 4. 检查是否有可以简化的子查询

    return suggestions
```

### 4.2 EXPLAIN 分析

> 对于需要深入分析的 SQL，优化器可能会使用 `EXPLAIN` 查看执行计划：

```python
# DuckDB 的 EXPLAIN 命令
EXPLAIN SELECT product_name, SUM(quantity * unit_price) as sales
FROM order_items
JOIN products ON order_items.product_id = products.product_id
GROUP BY product_name
ORDER BY sales DESC
LIMIT 5;
```

> EXPLAIN 输出会显示查询的执行步骤、使用的索引、预估行数等信息。

## 5. 查询执行器

> 代码在 `backend/app/db/query_runner.py`。
>
> SQL 校验通过后，由查询执行器执行。

```python
class QueryRunner:
    def execute(self, sql: str) -> Dict[str, Any]:
        start_time = time.time()
        try:
            with db_connection.get_session() as conn:
                result = conn.execute(sql)
                columns = [desc[0] for desc in result.description]
                rows = [list(row) for row in result.fetchall()]
                execution_time_ms = int((time.time() - start_time) * 1000)

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "execution_time_ms": execution_time_ms,
                    "row_count": len(rows)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                ...
            }
```

> **设计要点：**
>
> 1. 捕获所有异常，返回结构化的错误信息
> 2. 记录执行时间，方便性能分析
> 3. `rows` 转为列表（DuckDB 返回的是元组），方便 JSON 序列化

## 6. 完整的 SQL 处理流程

```text
用户问题
  → 意图解析：提取指标、维度、过滤条件
  → Schema 加载：获取表结构
  → SQL 生成：LLM 根据问题 + Schema + 意图生成 SQL
  → SQL 校验：AST 解析检查安全性，自动注入 LIMIT
  → SQL 执行：DuckDB 执行查询
  → 成功 → SQL 优化 → 答案生成
  → 失败 → SQL 修复 → SQL 校验 → SQL 执行（最多 3 次）
```

## 7. 下一步

> SQL 处理流程理解后，接下来学习：
>
> - **答案生成与 API 端点** — 了解如何将查询结果转换为自然语言回答
> - **前端开发** — 了解界面如何实现
