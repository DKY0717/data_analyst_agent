"""v0.6 分层意图与 Schema Grounding 确定性评测。"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.agents.clarification import clarification_engine
from app.agents.graph import AgentGraph
from app.agents.grounding import schema_grounder
from app.analysis_intent.rule_parser import AnalysisIntentRuleParser
from evaluation.intent_grounding_report_writer import IntentGroundingReportWriter


class IntentGroundingEvaluationRunner:
    """不调用 LLM、不访问数据库，专门评测 v0.6 分层链路的确定性部分。"""

    def __init__(
        self,
        case_file: str | Path | None = None,
        rule_parser: AnalysisIntentRuleParser | None = None,
        grounder=schema_grounder,
        clarification=clarification_engine,
    ):
        self.case_file = (
            Path(case_file)
            if case_file
            else Path(__file__).parent / "cases" / "intent_grounding_cases.yaml"
        )
        self.rule_parser = rule_parser or AnalysisIntentRuleParser()
        self.grounder = grounder
        self.clarification = clarification
        self.graph = AgentGraph()

    def load_cases(self) -> List[Dict[str, Any]]:
        with self.case_file.open("r", encoding="utf-8") as file:
            document = yaml.safe_load(file) or {}
        cases = document.get("cases")
        if not isinstance(cases, list):
            raise ValueError("case file must contain a cases list")
        return cases

    def evaluate_all(self) -> Dict[str, Any]:
        results = [self.evaluate_case(case) for case in self.load_cases()]
        return {"summary": self.summarize_results(results), "results": results}

    def evaluate_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        intent = self.rule_parser.parse(case["question"])
        grounding = self.grounder.ground(intent)
        clarification = self.clarification.check(intent)
        clarification_required = bool(
            clarification
            and self.graph._should_request_clarification(
                {
                    "question": case["question"],
                    "session_id": "evaluation-session",
                    "conversation_context": "",
                },
                intent,
            )
        )

        actual_metrics = [slot.concept for slot in intent.metrics]
        actual_dimensions = [slot.concept for slot in intent.dimensions]
        actual_filters = [
            {
                "concept": item.concept,
                "operator": item.operator,
                "value": item.value,
            }
            for item in intent.filters
        ]
        actual_candidate_ids = self._candidate_ids(grounding)
        actual_route_tables = grounding.get("schema_route", {}).get("selected_tables", [])
        actual_join_edges = [
            list(edge)
            for edge in grounding.get("schema_route", {}).get("join_edges", [])
        ]
        expected_route_tables = case.get("expected_route_tables", [])
        expected_join_edges = case.get("expected_join_edges", [])
        actual_option_ids = [
            option.candidate_id for option in clarification.options
        ] if clarification else []
        ranking = intent.ranking.model_dump() if intent.ranking else None

        checks = {
            "metrics_matched": self._set_match(actual_metrics, case.get("expected_metrics", [])),
            "dimensions_matched": self._set_match(
                actual_dimensions, case.get("expected_dimensions", [])
            ),
            "filters_matched": self._filters_match(
                actual_filters, case.get("expected_filters", [])
            ),
            "ranking_matched": self._ranking_match(ranking, case.get("expected_ranking")),
            "grounding_candidates_matched": self._contains_all(
                actual_candidate_ids, case.get("expected_candidate_ids", [])
            ),
            "route_tables_matched": self._set_match(
                actual_route_tables, expected_route_tables
            ),
            "route_join_edges_matched": self._edge_set_match(
                actual_join_edges, expected_join_edges
            ),
            "clarification_decision_matched": (
                clarification_required is bool(case.get("expected_clarification_required", False))
            ),
            "clarification_options_matched": self._contains_all(
                actual_option_ids,
                case.get("expected_clarification_option_ids", []),
            ),
        }

        return {
            "case_id": case["id"],
            "question": case["question"],
            "category": case["category"],
            "actual_metrics": actual_metrics,
            "actual_dimensions": actual_dimensions,
            "actual_filters": actual_filters,
            "actual_ranking": ranking,
            "actual_candidate_ids": actual_candidate_ids,
            "actual_route_tables": actual_route_tables,
            "actual_join_edges": actual_join_edges,
            "route_table_precision": self._set_precision(
                actual_route_tables, expected_route_tables
            ),
            "route_table_recall": self._set_recall(
                actual_route_tables, expected_route_tables
            ),
            "clarification_required": clarification_required,
            "clarification_option_ids": actual_option_ids,
            **checks,
            "passed": all(checks.values()),
        }

    def summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(results)
        summary = {
            "total_cases": total,
            "slot_match_rate": self._rate(
                sum(
                    item["metrics_matched"]
                    and item["dimensions_matched"]
                    and item["filters_matched"]
                    and item["ranking_matched"]
                    for item in results
                ),
                total,
            ),
            "grounding_candidate_hit_rate": self._rate(
                sum(item["grounding_candidates_matched"] for item in results),
                total,
            ),
            "route_table_recall_rate": self._average(
                [item["route_table_recall"] for item in results]
            ),
            "route_table_precision": self._average(
                [item["route_table_precision"] for item in results]
            ),
            "join_edge_accuracy": self._rate(
                sum(item["route_join_edges_matched"] for item in results), total
            ),
            "clarification_decision_accuracy": self._rate(
                sum(item["clarification_decision_matched"] for item in results),
                total,
            ),
            "clarification_option_hit_rate": self._rate(
                sum(item["clarification_options_matched"] for item in results),
                total,
            ),
            "all_expectations_met_rate": self._rate(
                sum(item["passed"] for item in results),
                total,
            ),
        }
        summary["passed"] = bool(results) and summary["all_expectations_met_rate"] == 1.0
        return summary

    @staticmethod
    def _candidate_ids(grounding: Dict[str, Any]) -> List[str]:
        ids: List[str] = []
        for group_name in ("metric_groundings", "dimension_groundings"):
            for grounding_item in grounding.get(group_name, []):
                ids.extend(
                    candidate.get("candidate_id", "")
                    for candidate in grounding_item.get("candidates", [])
                    if candidate.get("candidate_id")
                )
        return sorted(set(ids))

    @staticmethod
    def _set_match(actual: List[str], expected: List[str]) -> bool:
        return set(actual) == set(expected)

    @staticmethod
    def _contains_all(actual: List[str], expected: List[str]) -> bool:
        return set(expected).issubset(set(actual))

    @staticmethod
    def _edge_set_match(actual: List[List[str]], expected: List[List[str]]) -> bool:
        """JOIN 边忽略方向比较，但不允许额外或缺失路径。"""
        normalize = lambda edges: {
            frozenset((str(edge[0]), str(edge[1])))
            for edge in edges
            if isinstance(edge, (list, tuple)) and len(edge) == 2
        }
        return normalize(actual) == normalize(expected)

    @staticmethod
    def _set_precision(actual: List[str], expected: List[str]) -> float:
        actual_set = set(actual)
        expected_set = set(expected)
        if not actual_set:
            return 1.0 if not expected_set else 0.0
        return len(actual_set & expected_set) / len(actual_set)

    @staticmethod
    def _set_recall(actual: List[str], expected: List[str]) -> float:
        expected_set = set(expected)
        if not expected_set:
            return 1.0
        return len(set(actual) & expected_set) / len(expected_set)

    @staticmethod
    def _filters_match(actual: List[Dict[str, Any]], expected: List[Dict[str, Any]]) -> bool:
        normalized_actual = {
            (item.get("concept"), item.get("operator"), repr(item.get("value")))
            for item in actual
        }
        normalized_expected = {
            (item.get("concept"), item.get("operator"), repr(item.get("value")))
            for item in expected
        }
        return normalized_expected.issubset(normalized_actual)

    @staticmethod
    def _ranking_match(actual: Dict[str, Any] | None, expected: Dict[str, Any] | None) -> bool:
        if expected is None:
            return actual is None
        return actual == expected

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    @staticmethod
    def _average(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic intent grounding evaluation")
    parser.add_argument("--case-file")
    args = parser.parse_args(argv)
    try:
        report = IntentGroundingEvaluationRunner(case_file=args.case_file).evaluate_all()
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"Intent grounding evaluation input error: {type(exc).__name__}", file=sys.stderr)
        return 2

    paths = IntentGroundingReportWriter().write(report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Intent grounding evaluation report: {paths['markdown']}")
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
