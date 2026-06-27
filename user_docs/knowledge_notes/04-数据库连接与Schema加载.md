# 数据库连接与 Schema 加载

## 1. 学习目标

> - 理解 DuckDB 的连接管理方式
> - 了解上下文管理器（`with` 语句）在数据库操作中的作用
> - 看懂 Schema 加载器如何读取表结构
> - 理解 Schema 信息如何传递给 LLM 生成 SQL

## 2. 数据库连接管理

> 连接管理代码在 `backend/app/db/connection.py`。

### 2.1 连接工厂模式

```python
import duckdb
from contextlib import contextmanager

class DatabaseConnection:
    """数据库连接管理器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(settings.DATA_DIR / "database.duckdb")

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """每次调用创建一个全新的数据库连接"""
        conn = duckdb.connect(self.db_path)
        return conn

    @contextmanager
    def get_session(self):
        """上下文管理器：自动创建和关闭连接"""
        conn = self.get_connection()
        try:
            yield conn
        except Exception as e:
            raise DatabaseError(f"数据库会话错误: {e}")
        finally:
            conn.close()

# 全局单例
db_connection = DatabaseConnection()
```

> **为什么每次 `get_connection()` 都创建新连接？**
>
> Web 服务可能同时处理多个请求。如果所有请求共享同一个连接，会导致数据竞争。每次请求创建独立连接，用完就关闭，是最安全的做法。
>
> **上下文管理器的作用：**
>
> `@contextmanager` 装饰器让 `get_session()` 可以配合 `with` 使用：

```python
# 使用方式
with db_connection.get_session() as conn:
    result = conn.execute("SELECT COUNT(*) FROM orders").fetchone()
# 退出 with 块时，conn.close() 会自动调用
```

> 即使 `execute` 抛出异常，`finally` 中的 `conn.close()` 也会执行，不会泄漏连接。

### 2.2 为什么不用连接池

> DuckDB 是嵌入式数据库，不像 MySQL/PostgreSQL 那样需要网络连接池。DuckDB 的连接就是打开本地文件，开销很小。
>
> 但 DuckDB 有一个重要限制：**同一个数据库文件在同一时间只能有一个写连接**（读连接可以多个）。所以项目选择每次创建独立连接，用完即关。

## 3. Schema 加载器

> Schema 加载器在 `backend/app/db/schema_loader.py`，负责从数据库中读取表结构信息。
>
> LLM 生成 SQL 时需要知道数据库有哪些表、每个表有哪些列、列的类型是什么。Schema 加载器就是提供这些信息的。

### 3.1 获取所有表名

```python
def get_tables(self) -> List[str]:
    """获取数据库中所有表名"""
    with self.db.get_session() as conn:
        result = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchall()
        return [row[0] for row in result]
```

> `information_schema` 是 SQL 标准中的系统视图，所有关系型数据库都有。它存储了数据库的元数据（表名、列名、类型等）。
>
> `table_schema = 'main'` 是 DuckDB 的默认 schema，类似 PostgreSQL 的 `public`。

### 3.2 获取单表结构

```python
def get_table_schema(self, table_name: str) -> Dict[str, Any]:
    """获取指定表的结构信息"""
    with self.db.get_session() as conn:
        # 获取列信息
        columns = conn.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            ORDER BY ordinal_position
        """, [table_name]).fetchall()

        # 获取约束信息（主键、外键）
        constraints = conn.execute("""
            SELECT constraint_type, constraint_text, constraint_column_names
            FROM duckdb_constraints()
            WHERE schema_name = 'main' AND table_name = ?
        """, [table_name]).fetchall()

        primary_keys, foreign_keys = self._parse_constraints(constraints)

        return {
            "table_name": table_name,
            "columns": [
                {
                    "name": col[0],       # 列名
                    "type": col[1],       # 数据类型
                    "nullable": col[2] == "YES"  # 是否可为空
                }
                for col in columns
            ],
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
        }
```

> **查询参数用 `?` 占位符：**
>
> 不要用字符串拼接 SQL（`f"WHERE table_name = '{table_name}'"`），那样会导致 SQL 注入。使用 `?` 占位符让数据库驱动自动处理参数转义。

### 3.3 外键约束解析

> DuckDB 的 `duckdb_constraints()` 函数返回约束信息，但外键的引用表和引用列需要从约束文本中提取：

```python
@staticmethod
def _parse_constraints(constraints):
    primary_keys = []
    foreign_keys = []

    for constraint_type, constraint_text, column_names in constraints:
        if constraint_type == "PRIMARY KEY":
            primary_keys.extend(list(column_names or []))
        elif constraint_type == "FOREIGN KEY":
            # 从约束文本中提取引用表和引用列
            # 例如: "FOREIGN KEY (region_id) REFERENCES regions(region_id)"
            match = re.search(
                r"REFERENCES\s+([\w\"]+)\s*\(([^)]+)\)",
                constraint_text or "",
                re.IGNORECASE,
            )
            if match:
                referenced_table = match.group(1).strip('"')
                referenced_columns = match.group(2).split(",")
                for local_col, ref_col in zip(column_names, referenced_columns):
                    foreign_keys.append({
                        "column": local_col.strip().strip('"'),
                        "referenced_table": referenced_table,
                        "referenced_column": ref_col.strip().strip('"'),
                    })

    return primary_keys, foreign_keys
```

> 这段代码用正则表达式从 `FOREIGN KEY (region_id) REFERENCES regions(region_id)` 这样的文本中提取出引用关系。

### 3.4 获取完整 Schema

```python
def get_full_schema(self) -> Dict[str, Any]:
    """获取所有表的完整结构"""
    tables = self.get_tables()
    schema = {}
    for table in tables:
        schema[table] = self.get_table_schema(table)
    return {"tables": schema}
```

> 返回格式示例：

```json
{
  "tables": {
    "customers": {
      "table_name": "customers",
      "columns": [
        {"name": "customer_id", "type": "INTEGER", "nullable": false},
        {"name": "customer_name", "type": "VARCHAR", "nullable": true},
        {"name": "gender", "type": "VARCHAR", "nullable": true},
        {"name": "age", "type": "INTEGER", "nullable": true},
        {"name": "region_id", "type": "INTEGER", "nullable": true},
        {"name": "register_date", "type": "DATE", "nullable": true}
      ],
      "primary_keys": ["customer_id"],
      "foreign_keys": [
        {"column": "region_id", "referenced_table": "regions", "referenced_column": "region_id"}
      ]
    }
  }
}
```

## 4. Schema 如何被使用

> Schema 加载器的输出会经过以下流程：

```text
SchemaLoader.get_full_schema()
  → 返回 JSON 格式的表结构
  → 注入到 LLM 的 prompt 中
  → LLM 根据表结构生成 SQL
```

> 在 Agent 工作流的 `load_schema` 节点中：

```python
async def _load_schema(self, state: AgentState) -> Dict[str, Any]:
    """加载数据库 Schema，供后续 SQL 生成使用"""
    schema = schema_loader.get_full_schema()
    return {"schema_context": schema}
```

> 然后在 `generate_sql` 节点中，schema 会被传给 LLM：

```python
output = await sql_generator.generate(
    state["question"],           # 用户问题
    state["schema_context"],     # Schema 信息
    ...
)
```

## 5. 信息查询的 API 端点

> Schema 信息也通过 `/api/schema` 接口暴露给前端：

```python
@router.get("/api/schema", response_model=SuccessResponse)
async def get_schema():
    schema = schema_loader.get_full_schema()
    return SuccessResponse(code=200, message="success", data=SchemaResponse(**schema))
```

> 前端的 Schema 面板会调用这个接口，在界面上展示数据库的表结构，让用户了解系统"知道"哪些数据。

## 6. 关键设计决策总结

| 决策 | 原因 |
|------|------|
| 每次请求创建新连接 | 避免并发数据竞争 |
| 使用上下文管理器 | 确保连接一定被关闭 |
| 用 `?` 占位符 | 防止 SQL 注入 |
| 从 information_schema 读取 | SQL 标准，可移植 |
| 用正则解析外键文本 | DuckDB 0.9 不结构化返回引用信息 |
| 全局单例模式 | 整个应用共享一个加载器实例 |

## 7. 下一步

> 数据库连接和 Schema 加载理解后，接下来学习：
>
> - **SQL 安全防护** — 了解系统如何在 SQL 执行前拦截危险操作
> - **LLM 服务封装** — 了解如何调用大模型生成 SQL
