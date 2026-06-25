# 错误分类器测试

from app.security.error_classifier import classify_sql_error, SQLErrorCategory


def test_classify_column_not_found():
    result = classify_sql_error('Column "sales" does not exist')
    assert result.category == SQLErrorCategory.COLUMN_NOT_FOUND
    assert result.extracted_target == "sales"
    assert "列名" in result.repair_hint


def test_classify_table_not_found():
    result = classify_sql_error("Table orders does not exist")
    assert result.category == SQLErrorCategory.TABLE_NOT_FOUND
    assert result.extracted_target == "orders"


def test_classify_function_not_found():
    result = classify_sql_error("Function date_format does not exist")
    assert result.category == SQLErrorCategory.FUNCTION_NOT_FOUND
    assert result.extracted_target == "date_format"
    assert "STRFTIME" in result.repair_hint


def test_classify_type_mismatch():
    result = classify_sql_error("Cannot cast VARCHAR to INTEGER")
    assert result.category == SQLErrorCategory.TYPE_MISMATCH


def test_classify_ambiguous_column():
    result = classify_sql_error("Ambiguous column name: order_id")
    assert result.category == SQLErrorCategory.AMBIGUOUS_COLUMN


def test_classify_aggregate_misuse():
    result = classify_sql_error("column must appear in GROUP BY clause")
    assert result.category == SQLErrorCategory.AGGREGATE_MISUSE


def test_classify_syntax_error():
    result = classify_sql_error("Syntax error at position 10")
    assert result.category == SQLErrorCategory.SYNTAX


def test_classify_timeout():
    result = classify_sql_error("Query timed out after 30s")
    assert result.category == SQLErrorCategory.TIMEOUT


def test_classify_unknown_error():
    result = classify_sql_error("Some random error message")
    assert result.category == SQLErrorCategory.UNKNOWN
    assert result.repair_hint != ""


def test_classify_error_type_parameter():
    # error_type 参数用于补充匹配，但分类器主要依赖 error_message
    result = classify_sql_error("some error", error_type="TimeoutError")
    # error_type 不直接映射，仍按 error_message 匹配
    assert result.category == SQLErrorCategory.UNKNOWN
