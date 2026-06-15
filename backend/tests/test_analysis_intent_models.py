# 分层意图系统的跨模块数据契约测试
# 先锁定稳定字段与校验边界，避免后续解析器、Grounder 和 Router 各自发明结构。

import pytest
from pydantic import ValidationError

from app.analysis_intent.models import (
    AnalysisIntent,
    ClarificationRequest,
    GroundingCandidate,
    GroundingResult,
    IntentSlot,
    RankingSlot,
    SchemaRoute,
)


def test_analysis_intent_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        AnalysisIntent(task_types=["aggregation"], overall_confidence=1.1)


def test_analysis_intent_keeps_structured_slots():
    intent = AnalysisIntent(
        task_types=["aggregation", "ranking"],
        metrics=[
            IntentSlot(
                concept="sales_amount",
                confidence=0.96,
                evidence="销售额",
            )
        ],
        ranking=RankingSlot(direction="desc", limit=5),
        overall_confidence=0.95,
    )

    assert intent.metrics[0].concept == "sales_amount"
    assert intent.ranking.direction == "desc"
    assert intent.ranking.limit == 5


def test_grounding_and_route_keep_stable_evidence():
    candidate = GroundingCandidate(
        candidate_id="sales_by_order_total",
        concept="sales_amount",
        expression="SUM(orders.total_amount)",
        tables=["orders"],
        columns=["orders.total_amount"],
        score=0.9,
        evidence=["semantic_metric"],
    )
    grounding = GroundingResult(concept="sales_amount", candidates=[candidate])
    route = SchemaRoute(
        selected_tables=["orders"],
        join_edges=[],
        evidence={"orders": ["metric:sales_amount"]},
        confidence=0.9,
    )

    assert grounding.candidates[0].candidate_id == "sales_by_order_total"
    assert grounding.candidates[0].evidence == ["semantic_metric"]
    assert route.evidence["orders"] == ["metric:sales_amount"]


def test_clarification_requires_stable_candidate_ids():
    request = ClarificationRequest(
        clarification_id="clarify-sales-001",
        reason="metric_definition_ambiguity",
        question="销售额采用哪种计算口径？",
        options=[
            {
                "candidate_id": "sales_by_order_total",
                "label": "订单总金额",
                "description": "按 orders.total_amount 汇总",
            }
        ],
        max_rounds=2,
    )

    assert request.options[0].candidate_id == "sales_by_order_total"


def test_clarification_rejects_more_than_two_rounds():
    with pytest.raises(ValidationError):
        ClarificationRequest(
            clarification_id="clarify-sales-001",
            reason="metric_definition_ambiguity",
            question="销售额采用哪种计算口径？",
            options=[
                {
                    "candidate_id": "sales_by_order_total",
                    "label": "订单总金额",
                    "description": "按 orders.total_amount 汇总",
                }
            ],
            max_rounds=3,
        )
