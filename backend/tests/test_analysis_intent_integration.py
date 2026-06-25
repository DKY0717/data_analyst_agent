# v0.6 分层意图解析集成测试
# 测试 parse_intent 节点、Grounding 和 Clarification 的完整链路。

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.graph import AgentGraph
from app.agents.grounding import SchemaGrounder
from app.agents.clarification import ClarificationEngine
from app.analysis_intent.models import AnalysisIntent, IntentSlot, RankingSlot


class TestParseIntentNode:
    """测试 parse_intent 节点在 AgentGraph 中的行为"""

    @pytest.mark.asyncio
    async def test_parse_intent_extracts_metrics_and_dimensions(self):
        """规则解析器能从问题中提取指标和维度"""
        graph = AgentGraph()

        with patch("app.agents.graph.intent_guard") as mi:
            mi.validate.return_value = {"is_safe": True, "rule_id": None, "reason": None, "category": None}

            state = {
                "question": "统计各地区的销售额",
                "intent_is_safe": True,
                "llm_calls": [],
                "audit_events": [],
            }

            # 只测试 parse_intent 节点，mock 其他节点
            with patch.object(graph, "rule_parser") as mock_rule, \
                 patch.object(graph, "llm_parser") as mock_llm, \
                 patch.object(graph, "intent_merger") as mock_merger:

                rule_intent = AnalysisIntent(
                    metrics=[IntentSlot(concept="sales_amount", confidence=0.95, evidence="销售额")],
                    dimensions=[IntentSlot(concept="region", confidence=0.95, evidence="地区")],
                    overall_confidence=0.95,
                )
                mock_rule.parse.return_value = rule_intent
                mock_llm.parse = AsyncMock(side_effect=Exception("LLM unavailable"))
                mock_merger.merge.return_value = rule_intent

                result = await graph._parse_intent(state)

        assert result["analysis_intent"] is not None
        assert len(result["analysis_intent"]["metrics"]) == 1
        assert result["analysis_intent"]["metrics"][0]["concept"] == "sales_amount"
        assert "grounding" not in result["analysis_intent"]
        assert "clarification" not in result["analysis_intent"]

    def test_graph_grounding_node_adds_schema_evidence(self):
        graph = AgentGraph()
        intent = AnalysisIntent(
            metrics=[IntentSlot(concept="sales_amount", confidence=0.95, evidence="销售额")],
            dimensions=[IntentSlot(concept="region", confidence=0.95, evidence="地区")],
            overall_confidence=0.95,
        )

        result = graph._ground_schema({"analysis_intent": intent.model_dump(), "audit_events": []})

        assert "grounding_result" in result
        assert result["analysis_intent"]["grounding"] == result["grounding_result"]
        assert "orders" in result["grounding_result"]["schema_route"]["selected_tables"]

    def test_graph_clarification_node_pauses_only_after_grounding(self):
        graph = AgentGraph()
        intent = AnalysisIntent(missing_slots=["metric"], overall_confidence=0.0)
        grounding = {"schema_route": {"selected_tables": []}}

        result = graph._assess_clarification(
            {
                "question": "帮我分析一下",
                "session_id": "session-1",
                "conversation_context": "",
                "analysis_intent": intent.model_dump(),
                "grounding_result": grounding,
                "audit_events": [],
            }
        )

        assert result["status"] == "clarification_required"
        assert result["analysis_intent"]["grounding"] == grounding
        assert result["analysis_intent"]["clarification"]["clarification_id"].startswith("clarify_")


class TestSchemaGrounder:
    """测试 Grounding 将业务概念映射到物理 Schema"""

    def test_ground_metric_maps_to_expression(self):
        """指标概念应映射到语义层定义的表达式"""
        grounder = SchemaGrounder()
        intent = AnalysisIntent(
            metrics=[IntentSlot(concept="sales_amount", confidence=0.95, evidence="销售额")],
            overall_confidence=0.95,
        )

        result = grounder.ground(intent)

        assert len(result["metric_groundings"]) == 1
        mg = result["metric_groundings"][0]
        assert mg["concept"] == "sales_amount"
        assert len(mg["candidates"]) >= 1
        assert "SUM(orders.total_amount)" in mg["candidates"][0]["expression"]

    def test_ground_dimension_maps_to_fields(self):
        """维度概念应映射到语义层定义的字段"""
        grounder = SchemaGrounder()
        intent = AnalysisIntent(
            dimensions=[IntentSlot(concept="region", confidence=0.95, evidence="地区")],
            overall_confidence=0.95,
        )

        result = grounder.ground(intent)

        assert len(result["dimension_groundings"]) == 1
        dg = result["dimension_groundings"][0]
        assert dg["concept"] == "region"
        assert len(dg["candidates"]) >= 1
        assert "regions.region_name" in dg["candidates"][0]["expression"]

    def test_ground_includes_dimension_overrides(self):
        """按类别拆分销售额时应产生覆盖候选"""
        grounder = SchemaGrounder()
        intent = AnalysisIntent(
            metrics=[IntentSlot(concept="sales_amount", confidence=0.95, evidence="销售额")],
            dimensions=[IntentSlot(concept="category", confidence=0.95, evidence="类别")],
            overall_confidence=0.95,
        )

        result = grounder.ground(intent)
        mg = result["metric_groundings"][0]

        # 应有默认候选和维度覆盖候选
        assert len(mg["candidates"]) >= 2
        expressions = [c["expression"] for c in mg["candidates"]]
        assert any("order_items" in e for e in expressions)

    def test_ground_unknown_concept_returns_empty(self):
        """未知概念应返回空候选"""
        grounder = SchemaGrounder()
        intent = AnalysisIntent(
            metrics=[IntentSlot(concept="unknown_metric", confidence=0.5, evidence="未知")],
            overall_confidence=0.5,
        )

        result = grounder.ground(intent)
        assert result["metric_groundings"][0]["candidates"] == []

    def test_ground_builds_schema_route(self):
        """Grounding 应构建包含所需表的 Schema 路由"""
        grounder = SchemaGrounder()
        intent = AnalysisIntent(
            metrics=[IntentSlot(concept="sales_amount", confidence=0.95, evidence="销售额")],
            dimensions=[IntentSlot(concept="region", confidence=0.95, evidence="地区")],
            overall_confidence=0.95,
        )

        result = grounder.ground(intent)
        route = result["schema_route"]

        assert "orders" in route["selected_tables"]
        assert "regions" in route["selected_tables"]


class TestClarificationEngine:
    """测试澄清引擎的判断逻辑"""

    def test_high_confidence_no_clarification(self):
        """高置信度且无缺失槽位时不需要澄清"""
        engine = ClarificationEngine()
        intent = AnalysisIntent(
            metrics=[IntentSlot(concept="sales_amount", confidence=0.95, evidence="销售额")],
            overall_confidence=0.95,
        )

        result = engine.check(intent)
        assert result is None

    def test_missing_metric_triggers_clarification(self):
        """缺失指标时应触发澄清"""
        engine = ClarificationEngine()
        intent = AnalysisIntent(
            missing_slots=["metric"],
            overall_confidence=0.0,
        )

        result = engine.check(intent)
        assert result is not None
        assert "指标" in result.reason or "指标" in result.question
        assert len(result.options) > 0

    def test_low_confidence_triggers_clarification(self):
        """低置信度时应触发澄清"""
        engine = ClarificationEngine()
        intent = AnalysisIntent(
            metrics=[IntentSlot(concept="something", confidence=0.3, evidence="模糊")],
            overall_confidence=0.3,
        )

        result = engine.check(intent)
        assert result is not None
        assert result.max_rounds == 2

    def test_metrics_without_dimensions_suggests_dimensions(self):
        """有指标但无维度时推荐常见维度"""
        engine = ClarificationEngine()
        intent = AnalysisIntent(
            metrics=[IntentSlot(concept="sales_amount", confidence=0.95, evidence="销售额")],
            missing_slots=["dimension"],
            overall_confidence=0.4,
        )

        result = engine.check(intent)
        assert result is not None
        labels = [opt.label for opt in result.options]
        assert any("地区" in l for l in labels)
