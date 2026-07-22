# 高确定性规则意图解析器测试
# 规则层只负责可解释槽位，未知业务概念必须留给 LLM 或主动澄清处理。

from app.analysis_intent.rule_parser import AnalysisIntentRuleParser


def test_rule_parser_extracts_time_ranking_and_dimension():
    intent = AnalysisIntentRuleParser().parse(
        "统计 2024 年各地区销售额，找出最高的 5 个地区"
    )

    assert "aggregation" in intent.task_types
    assert "ranking" in intent.task_types
    assert intent.metrics[0].concept == "sales_amount"
    assert intent.metrics[0].evidence == "销售额"
    assert intent.dimensions[0].concept == "region"
    assert intent.filters[0].concept == "order_date"
    assert intent.filters[0].operator == "year_equals"
    assert intent.filters[0].value == 2024
    assert intent.ranking.direction == "desc"
    assert intent.ranking.limit == 5


def test_rule_parser_extracts_multiple_metrics_without_duplicates():
    intent = AnalysisIntentRuleParser().parse("对比各地区销售额、订单金额和订单数")

    assert [slot.concept for slot in intent.metrics] == [
        "sales_amount",
        "order_count",
    ]
    assert [slot.concept for slot in intent.dimensions] == ["region"]


def test_rule_parser_keeps_geographic_granularities_independent():
    """显式省份或城市问题不能再被折叠成宽泛的 region 三字段维度。"""
    province_intent = AnalysisIntentRuleParser().parse("按省份统计销售额")
    city_intent = AnalysisIntentRuleParser().parse("按城市统计销售额")

    assert [slot.concept for slot in province_intent.dimensions] == ["province"]
    assert [slot.concept for slot in city_intent.dimensions] == ["city"]


def test_rule_parser_distinguishes_product_from_product_category():
    """“商品”是单品维度，而“商品类别”必须优先命中更长的类别别名。"""
    product_intent = AnalysisIntentRuleParser().parse("找出销售额最高的 5 个商品")
    category_intent = AnalysisIntentRuleParser().parse("统计各商品类别的销售额")

    assert [slot.concept for slot in product_intent.dimensions] == ["product"]
    assert [slot.concept for slot in category_intent.dimensions] == ["category"]


def test_rule_parser_extracts_ascending_ranking():
    intent = AnalysisIntentRuleParser().parse("找出订单数最少的前 3 个地区")

    assert intent.ranking.direction == "asc"
    assert intent.ranking.limit == 3


def test_rule_parser_does_not_invent_unknown_metric():
    intent = AnalysisIntentRuleParser().parse("分析一下经营情况")

    assert intent.metrics == []
    assert "metric" in intent.missing_slots
