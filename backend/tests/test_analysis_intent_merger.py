# 规则与 LLM 意图合并测试
# 合并器不得静默覆盖冲突，高确定性规则槽位应保持稳定。

from app.analysis_intent.merger import AnalysisIntentMerger
from app.analysis_intent.models import AnalysisIntent, IntentSlot, RankingSlot


def test_merger_keeps_conflicting_metric_candidates():
    rule = AnalysisIntent(
        metrics=[
            IntentSlot(
                concept="sales_amount",
                confidence=0.9,
                evidence="销售额",
            )
        ],
        overall_confidence=0.9,
    )
    llm = AnalysisIntent(
        metrics=[
            IntentSlot(
                concept="order_count",
                confidence=0.8,
                evidence="模型候选",
            )
        ],
        overall_confidence=0.8,
    )

    merged = AnalysisIntentMerger().merge(rule, llm)

    assert [slot.concept for slot in merged.metrics] == [
        "sales_amount",
        "order_count",
    ]
    assert merged.conflicts[0]["slot"] == "metrics"
    assert merged.overall_confidence < 0.9


def test_merger_deduplicates_matching_slots_and_prefers_rule_ranking():
    rule = AnalysisIntent(
        task_types=["aggregation", "ranking"],
        metrics=[
            IntentSlot(
                concept="sales_amount",
                confidence=0.95,
                evidence="销售额",
            )
        ],
        ranking=RankingSlot(direction="desc", limit=5),
        overall_confidence=0.95,
    )
    llm = AnalysisIntent(
        task_types=["ranking", "aggregation"],
        metrics=[
            IntentSlot(
                concept="sales_amount",
                confidence=0.8,
                evidence="LLM",
            )
        ],
        ranking=RankingSlot(direction="desc", limit=10),
        overall_confidence=0.8,
    )

    merged = AnalysisIntentMerger().merge(rule, llm)

    assert merged.task_types == ["aggregation", "ranking"]
    assert len(merged.metrics) == 1
    assert merged.metrics[0].evidence == "销售额"
    assert merged.ranking.limit == 5
    assert merged.conflicts[0]["slot"] == "ranking"
