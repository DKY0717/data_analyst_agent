# 语义层测试
# 这些测试定义 v0.3 业务语义层的最小可用能力：指标、维度、别名和 LLM 摘要。

from app.semantic.semantic_loader import SemanticLoader


def test_find_metric_by_chinese_alias():
    """能通过中文别名找到销售额指标"""
    loader = SemanticLoader()

    metric = loader.find_metric("销售额")

    assert metric["key"] == "sales_amount"
    assert metric["expression"] == "SUM(orders.total_amount)"


def test_find_metric_by_business_alias():
    """能通过业务常用别名找到退款率指标"""
    loader = SemanticLoader()

    metric = loader.find_metric("售后率")

    assert metric["key"] == "refund_rate"
    assert "refunds" in metric["expression"]
    assert "orders.order_id = refunds.order_id" in metric["required_joins"]


def test_find_dimension_by_alias():
    """能通过别名找到地区维度和它需要的 JOIN 关系"""
    loader = SemanticLoader()

    dimension = loader.find_dimension("城市")

    assert dimension["key"] == "region"
    assert "regions.city" in dimension["fields"]
    assert "orders.customer_id = customers.customer_id" in dimension["required_joins"]


def test_defaults_include_time_field_and_limit():
    """默认配置要包含时间字段和返回上限，供 SQL 生成 prompt 使用"""
    loader = SemanticLoader()

    defaults = loader.get_defaults()

    assert defaults["time_field"] == "orders.order_date"
    assert defaults["limit"] == 1000


def test_format_for_prompt_contains_metrics_dimensions_and_defaults():
    """格式化摘要必须适合直接拼进 LLM prompt"""
    loader = SemanticLoader()

    summary = loader.format_for_prompt()

    assert "业务指标:" in summary
    assert "销售额 = SUM(orders.total_amount)" in summary
    assert "退款率 =" in summary
    assert "业务维度:" in summary
    assert "地区:" in summary
    assert "默认时间字段: orders.order_date" in summary


def test_quarter_dimension_uses_duckdb_supported_expression():
    """季度维度应给出 DuckDB 可执行表达式，避免 LLM 猜测不存在的 %q/%Q 格式符。"""
    loader = SemanticLoader()

    dimension = loader.find_dimension("季度")

    assert dimension is not None
    assert any("EXTRACT(QUARTER FROM orders.order_date)" in field for field in dimension["fields"])
