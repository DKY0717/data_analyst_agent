# Schema 格式化工具函数
# 供 SQL Generator、SQL Repair Agent 等模块复用，避免重复代码

from typing import Any, Dict


def format_physical_schema(schema_context: Dict[str, Any]) -> str:
    """
    将 Schema 字典格式化为 LLM 可读的物理表结构文本

    输入格式示例:
    {
        "tables": {
            "orders": {
                "table_name": "orders",
                "columns": [{"name": "id", "type": "INTEGER", "nullable": False}, ...],
                "primary_keys": ["id"]
            }
        }
    }

    输出格式:
    表名: orders
      主键: id
      字段:
        - id (INTEGER, NOT NULL)
        - customer_id (INTEGER, NULLABLE)
    """
    tables = schema_context.get("tables", {})
    lines = []

    for table_name, table_info in tables.items():
        lines.append(f"表名: {table_name}")

        primary_keys = table_info.get("primary_keys", [])
        if primary_keys:
            lines.append(f"  主键: {', '.join(primary_keys)}")

        columns = table_info.get("columns", [])
        lines.append("  字段:")
        for col in columns:
            nullable = "NULLABLE" if col.get("nullable") else "NOT NULL"
            lines.append(f"    - {col['name']} ({col['type']}, {nullable})")

        lines.append("")

    return "\n".join(lines)
