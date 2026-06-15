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


def test_rule_parser_extracts_ascending_ranking():
    intent = AnalysisIntentRuleParser().parse("找出订单数最少的前 3 个地区")

    assert intent.ranking.direction == "asc"
    assert intent.ranking.limit == 3


def test_rule_parser_does_not_invent_unknown_metric():
    intent = AnalysisIntentRuleParser().parse("分析一下经营情况")

    assert intent.metrics == []
    assert "metric" in intent.missing_slots
