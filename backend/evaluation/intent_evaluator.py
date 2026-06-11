"""使用固定 case 量化 Intent Guard 的阻断率与误杀率。"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.security.intent_guard import intent_guard
from evaluation.intent_report_writer import IntentReportWriter


class IntentEvaluationRunner:
    """运行不依赖 LLM 和数据库的确定性危险意图评测。"""

    def __init__(self, guard=intent_guard, case_file: str | Path | None = None):
        self.guard = guard
        self.case_file = (
            Path(case_file)
            if case_file
            else Path(__file__).parent / "cases" / "unsafe_intent_cases.yaml"
        )

    def load_cases(self) -> List[Dict[str, Any]]:
        with self.case_file.open("r", encoding="utf-8") as file:
            document = yaml.safe_load(file) or {}
        cases = document.get("cases")
        if not isinstance(cases, list):
            raise ValueError("case file must contain a cases list")
        return cases

    def evaluate_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        decision = self.guard.validate(case["question"])
        expected_safe = bool(case["expected_safe"])
        actual_safe = bool(decision["is_safe"])
        expected_rule_id = case.get("expected_rule_id")
        actual_rule_id = decision.get("rule_id")
        return {
            "case_id": case["id"],
            "question": case["question"],
            "category": case["category"],
            "expected_safe": expected_safe,
            "actual_safe": actual_safe,
            "expected_rule_id": expected_rule_id,
            "actual_rule_id": actual_rule_id,
            "decision_matched": expected_safe == actual_safe,
            "rule_matched": expected_rule_id == actual_rule_id,
            "reason": decision.get("reason"),
        }

    def evaluate_all(self) -> Dict[str, Any]:
        results = [self.evaluate_case(case) for case in self.load_cases()]
        return {"summary": self.summarize_results(results), "results": results}

    def summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        unsafe = [item for item in results if not item["expected_safe"]]
        safe = [item for item in results if item["expected_safe"]]
        blocked_unsafe = sum(not item["actual_safe"] for item in unsafe)
        passed_safe = sum(item["actual_safe"] for item in safe)
        false_positives = sum(not item["actual_safe"] for item in safe)
        matched_rules = sum(item["rule_matched"] for item in results)

        summary = {
            "total_cases": len(results),
            "unsafe_case_count": len(unsafe),
            "safe_case_count": len(safe),
            "unsafe_intent_block_rate": self._rate(blocked_unsafe, len(unsafe)),
            "safe_intent_pass_rate": self._rate(passed_safe, len(safe)),
            "false_positive_rate": self._rate(false_positives, len(safe)),
            "expected_rule_match_rate": self._rate(matched_rules, len(results)),
            "rule_hit_counts": dict(
                Counter(item["actual_rule_id"] for item in results if item["actual_rule_id"])
            ),
        }
        summary["passed"] = bool(results) and (
            summary["unsafe_intent_block_rate"] == 1.0
            and summary["safe_intent_pass_rate"] == 1.0
            and summary["false_positive_rate"] == 0.0
            and summary["expected_rule_match_rate"] == 1.0
        )
        return summary

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic intent evaluation")
    parser.add_argument("--case-file")
    args = parser.parse_args(argv)
    try:
        report = IntentEvaluationRunner(case_file=args.case_file).evaluate_all()
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"Intent evaluation input error: {type(exc).__name__}", file=sys.stderr)
        return 2
    paths = IntentReportWriter().write(report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Intent evaluation report: {paths['markdown']}")
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
