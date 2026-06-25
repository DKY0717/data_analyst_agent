# SQL 错误分类器
# 将数据库执行错误分为不同类别，用于差异化修复策略

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SQLErrorCategory(Enum):
    """SQL 错误分类"""
    SYNTAX = "syntax"                    # SQL 语法错误
    COLUMN_NOT_FOUND = "column_not_found"  # 列名不存在
    TABLE_NOT_FOUND = "table_not_found"    # 表名不存在
    FUNCTION_NOT_FOUND = "function_not_found"  # 函数不存在
    TYPE_MISMATCH = "type_mismatch"        # 类型不匹配
    AMBIGUOUS_COLUMN = "ambiguous_column"  # 列名歧义
    AGGREGATE_MISUSE = "aggregate_misuse"  # 聚合函数误用
    CONSTRAINT_VIOLATION = "constraint_violation"  # 约束违反
    TIMEOUT = "timeout"                    # 查询超时
    UNKNOWN = "unknown"                    # 未知错误


@dataclass
class ClassifiedError:
    """分类后的错误信息"""
    category: SQLErrorCategory
    original_message: str
    extracted_target: Optional[str] = None  # 提取的列名/表名/函数名
    repair_hint: str = ""  # 给 LLM 的修复提示


# 错误模式匹配规则：(正则表达式, 错误分类, 提取组索引, 修复提示)
_ERROR_PATTERNS = [
    # 列名不存在
    (
        re.compile(r"(?:Column|column|字段)\s+[\"']?(\w+)[\"']?\s+(?:does not exist|not found|不存在|未找到)", re.IGNORECASE),
        SQLErrorCategory.COLUMN_NOT_FOUND,
        1,
        "列名不存在，请检查表结构中是否有该列，或是否使用了中文别名。"
    ),
    # 表名不存在
    (
        re.compile(r"(?:Table|table|表)\s+[\"']?(\w+)[\"']?\s+(?:does not exist|not found|不存在|未找到)", re.IGNORECASE),
        SQLErrorCategory.TABLE_NOT_FOUND,
        1,
        "表名不存在，请检查 Schema 中的表名列表。"
    ),
    # 函数不存在
    (
        re.compile(r"(?:Function|function|函数)\s+[\"']?(\w+)[\"']?\s+(?:does not exist|not found|不存在)", re.IGNORECASE),
        SQLErrorCategory.FUNCTION_NOT_FOUND,
        1,
        "函数不存在。DuckDB 常用函数：用 STRFTIME 代替 DATE_FORMAT，用 COALESCE 代替 IFNULL，用 EXTRACT(QUARTER FROM date) 提取季度。"
    ),
    # 类型不匹配
    (
        re.compile(r"(?:type|类型|mismatch|不匹配|cannot cast|无法转换|conversion)", re.IGNORECASE),
        SQLErrorCategory.TYPE_MISMATCH,
        None,
        "类型不匹配。字符串参与算术前必须 CAST 为数值类型，日期比较前确保格式一致。"
    ),
    # 列名歧义
    (
        re.compile(r"(?:ambiguous|歧义|Ambiguous)", re.IGNORECASE),
        SQLErrorCategory.AMBIGUOUS_COLUMN,
        None,
        "列名歧义。多表 JOIN 后同名列需要加表别名前缀，如 o.order_id 而非 order_id。"
    ),
    # 聚合函数误用
    (
        re.compile(r"(?:must appear in GROUP BY|GROUP BY|聚合|aggregate)", re.IGNORECASE),
        SQLErrorCategory.AGGREGATE_MISUSE,
        None,
        "聚合函数使用错误。SELECT 中的非聚合列必须出现在 GROUP BY 子句中。"
    ),
    # 语法错误
    (
        re.compile(r"(?:syntax error|语法错误|Syntax error|PARSE_ERROR|Parser Error)", re.IGNORECASE),
        SQLErrorCategory.SYNTAX,
        None,
        "SQL 语法错误。检查括号匹配、逗号分隔、关键字拼写。DuckDB 不支持 LIMIT offset, count 语法。"
    ),
    # 超时
    (
        re.compile(r"(?:timeout|超时|timed out|statement timeout)", re.IGNORECASE),
        SQLErrorCategory.TIMEOUT,
        None,
        "查询超时。尝试添加 WHERE 条件缩小范围，或减少 JOIN 表数量。"
    ),
]


def classify_sql_error(error_message: str, error_type: str = "") -> ClassifiedError:
    """将 SQL 错误信息分类

    Args:
        error_message: 数据库返回的错误信息
        error_type: Python 异常类型名

    Returns:
        ClassifiedError: 包含分类、提取的目标和修复提示
    """
    for pattern, category, group_idx, hint in _ERROR_PATTERNS:
        match = pattern.search(error_message)
        if match:
            target = match.group(group_idx) if group_idx else None
            return ClassifiedError(
                category=category,
                original_message=error_message,
                extracted_target=target,
                repair_hint=hint,
            )

    return ClassifiedError(
        category=SQLErrorCategory.UNKNOWN,
        original_message=error_message,
        repair_hint="请检查 SQL 语法和表结构是否匹配。"
    )
