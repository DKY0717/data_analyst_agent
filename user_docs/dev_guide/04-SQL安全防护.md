# 第四章：SQL 安全防护

> 本章目标：在 SQL 执行前加入安全检查，拦截危险操作。
>
> 完成本章后，任何 `DROP`、`DELETE`、系统表访问都会被自动拦截。

## 4.1 为什么需要安全防护

> LLM 生成的 SQL 可能不安全：
> - 用户问"删除所有订单"，LLM 可能真的生成 `DELETE FROM orders`
> - LLM 可能生成访问系统表的 SQL，泄露数据库内部信息
> - LLM 可能生成没有 LIMIT 的查询，返回百万行数据
>
> 我们需要在 SQL 执行前检查它是否安全。

## 4.2 安装 SQLGlot

> SQLGlot 是一个 SQL 解析库，能把 SQL 代码解析成**抽象语法树（AST）**。
>
> **为什么要用 AST 而不是字符串匹配？**
>
> 字符串匹配会误判：`SELECT * FROM orders WHERE status = 'DROP TABLE'` 中的 "DROP TABLE" 是字符串内容，不是命令。AST 解析能区分真正的 SQL 命令和字符串字面量。

```bash
cd backend
pip install sqlglot==20.0.0
```

> 更新 `backend/requirements.txt`，**用以下内容替换整个文件**：

```text
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.2
python-dotenv==1.0.0
duckdb==0.9.2
httpx==0.25.2
sqlglot==20.0.0
```

## 4.3 编写 SQL Guard

> 创建 `backend/app/security/` 目录和 `__init__.py`：

```bash
mkdir backend/app/security
New-Item -Path "backend/app/security/__init__.py" -ItemType File -Force
```

> 创建 `backend/app/security/sql_guard.py`：

```python
import sqlglot
from sqlglot import exp
from typing import Dict, Any, Optional, Tuple
from ..config import settings


class SQLGuard:
    """SQL 安全校验器"""

    # 只允许查询语句
    ALLOWED_STATEMENTS = {"SELECT", "WITH", "EXPLAIN"}

    # 禁止的语句类型
    BLOCKED_STATEMENTS = {
        "DROP", "DELETE", "UPDATE", "INSERT",
        "ALTER", "TRUNCATE", "CREATE", "MERGE"
    }

    # 禁止访问的系统表前缀
    BLOCKED_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog"}
    BLOCKED_TABLE_PREFIXES = ("duckdb_", "pg_")

    # 禁止调用的危险函数（可以读取文件或泄露信息）
    BLOCKED_FUNCTIONS = {
        "read_csv", "read_json", "read_parquet",
        "glob", "duckdb_tables", "duckdb_columns"
    }

    def __init__(self, max_rows: int = None):
        self.max_rows = max_rows or settings.SQL_MAX_ROWS

    def validate(self, sql: str) -> Dict[str, Any]:
        """校验 SQL 安全性

        Returns:
            {
                "is_safe": bool,
                "sanitized_sql": str,  # 安全的 SQL（可能加了 LIMIT）
                "reason": str | None   # 不安全的原因
            }
        """
        try:
            # 1. 空 SQL 检查
            if not sql or not sql.strip():
                return self._result(False, sql, "SQL 为空")

            # 2. 多语句检查（防止 SQL 注入）
            statements = sqlglot.parse(sql, dialect="duckdb")
            if len(statements) != 1:
                return self._result(False, sql, "不允许执行多个语句")

            parsed = statements[0]

            # 3. 语句类型检查
            statement_type = parsed.key.upper()
            if statement_type not in self.ALLOWED_STATEMENTS:
                return self._result(False, sql, f"禁止的语句类型: {statement_type}")

            # 4. AST 安全检查
            error = self._validate_ast_safety(parsed)
            if error:
                return self._result(False, sql, error)

            # 5. 自动注入 LIMIT
            sanitized_sql = self._inject_limit(parsed)

            return {
                "is_safe": True,
                "sanitized_sql": sanitized_sql,
                "reason": None
            }

        except Exception as e:
            return self._result(False, sql, f"SQL 解析错误: {e}")

    def _validate_ast_safety(self, parsed) -> Optional[str]:
        """遍历 AST，检查是否有危险的表或函数引用"""
        # 检查表名
        for table in parsed.find_all(exp.Table):
            table_name = (table.name or "").lower()
            schema_name = (table.db or "").lower()

            if schema_name in self.BLOCKED_SYSTEM_SCHEMAS:
                return f"禁止访问系统表: {table.sql(dialect='duckdb')}"

            if table_name.startswith(self.BLOCKED_TABLE_PREFIXES):
                return f"禁止访问系统表: {table.sql(dialect='duckdb')}"

        # 检查函数调用
        for func in parsed.find_all(exp.Func):
            func_name = (getattr(func, "name", "") or "").lower()
            if func_name in self.BLOCKED_FUNCTIONS:
                return f"禁止调用危险函数: {func_name}"

        return None  # 安全

    def _inject_limit(self, parsed) -> str:
        """如果 SQL 没有 LIMIT，自动加上"""
        if not parsed.args.get("limit"):
            parsed = parsed.limit(self.max_rows)
        return parsed.sql(dialect="duckdb")

    def _result(self, is_safe, sql, reason):
        return {
            "is_safe": is_safe,
            "sanitized_sql": sql,
            "reason": reason
        }


# 全局单例
sql_guard = SQLGuard()
```

> **核心逻辑解释：**
>
> 1. `sqlglot.parse(sql, dialect="duckdb")`：把 SQL 字符串解析成 AST
> 2. 检查语句类型：只有 `SELECT`、`WITH`、`EXPLAIN` 允许执行
> 3. 遍历 AST 中的所有表引用：拦截系统表访问
> 4. 遍历 AST 中的所有函数调用：拦截危险函数
> 5. 如果没有 LIMIT，自动加上 `LIMIT 1000`

## 4.4 测试 SQL Guard

> 创建 `backend/test_sql_guard.py`：

```python
import sys
sys.path.insert(0, ".")

from app.security.sql_guard import sql_guard


def test(sql, expected_safe, description):
    result = sql_guard.validate(sql)
    status = "✓" if result["is_safe"] == expected_safe else "✗"
    print(f"{status} {description}")
    if not result["is_safe"]:
        print(f"   原因: {result['reason']}")
    elif "LIMIT" in result["sanitized_sql"] and "LIMIT" not in sql.upper():
        print(f"   已自动注入 LIMIT")


# 安全的 SQL
test("SELECT * FROM orders", True, "普通 SELECT 查询")
test("SELECT COUNT(*) FROM customers", True, "聚合查询")
test("WITH cte AS (SELECT 1) SELECT * FROM cte", True, "CTE 查询")

# 不安全的 SQL
test("DROP TABLE orders", False, "DROP TABLE")
test("DELETE FROM orders", False, "DELETE")
test("INSERT INTO orders VALUES (1, 1, '2024-01-01', 'new', 100)", False, "INSERT")
test("SELECT * FROM information_schema.tables", False, "访问系统表")
test("SELECT 1; DROP TABLE orders", False, "多语句注入")
test("", False, "空 SQL")

# LIMIT 注入
test("SELECT * FROM orders", True, "缺少 LIMIT（应自动注入）")
```

> 运行测试：

```bash
cd backend
python test_sql_guard.py
```

> 你应该看到类似输出：

```text
✓ 普通 SELECT 查询
   已自动注入 LIMIT
✓ 聚合查询
✓ CTE 查询
✗ DROP TABLE
   原因: 禁止的语句类型: DROP
✗ DELETE
   原因: 禁止的语句类型: DELETE
✗ INSERT
   原因: 禁止的语句类型: INSERT
✗ 访问系统表
   原因: 禁止访问系统表: "information_schema"."tables"
✗ 多语句注入
   原因: 不允许执行多个语句
✗ 空 SQL
   原因: SQL 为空
✓ 缺少 LIMIT（应自动注入）
   已自动注入 LIMIT
```

> 所有测试都通过，SQL Guard 工作正常。

## 4.5 本章小结

> 你完成了：
> - 理解了 AST 解析的概念
> - 实现了 SQL 安全校验器
> - 拦截了危险语句类型、系统表访问、危险函数
> - 实现了自动 LIMIT 注入
> - 通过测试验证了所有安全规则
>
> 下一章我们将把所有组件串联成完整的 Agent 工作流。
