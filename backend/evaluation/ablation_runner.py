"""v0.6 分层意图/Grounding 消融实验运行器。"""

import argparse
import json
import sys
from typing import Any, Dict

from app.agents.grounding import schema_grounder
from app.analysis_intent.models import AnalysisIntent
from evaluation.intent_grounding_evaluator import IntentGroundingEvaluationRunner


ABLATION_MODES = (
    "full",
    "without_rule_parser",
    "without_graph_router",
    "without_clarification",
)


class EmptyRuleParser:
    """禁用规则解析，用来观察没有确定性槽位提取时的整体退化。"""

    def parse(self, question: str) -> AnalysisIntent:
        # 缺失指标会触发澄清，但不会产生可 Grounding 的指标/维度槽位。
        return AnalysisIntent(missing_slots=["metric"], overall_confidence=0.0)


class RouteDisabledGrounder:
    """保留候选 Grounding，仅移除路由结果，隔离图路由组件的贡献。"""

    def ground(self, intent: AnalysisIntent) -> Dict[str, Any]:
        grounding = schema_grounder.ground(intent)
        # 消融只关闭路由，不影响候选映射，便于面试时解释每层贡献。
        grounding["schema_route"] = {
            "selected_tables": [],
            "join_edges": [],
            "evidence": {},
            "confidence": 0.0,
        }
        return grounding


class ClarificationDisabledEngine:
    """禁用主动澄清，用来量化模糊问题无人追问时的失败率。"""

    def check(self, intent: AnalysisIntent):
        return None


class IntentGroundingAblationRunner:
    """围绕同一批 case 运行四种模式，输出可横向比较的分层指标。"""

    def __init__(self, case_file: str | None = None):
        self.case_file = case_file

    def run_all(self) -> Dict[str, Any]:
        mode_reports = {
            mode: self._runner_for_mode(mode).evaluate_all()
            for mode in ABLATION_MODES
        }
        mode_summaries = {
            mode: report["summary"]
            for mode, report in mode_reports.items()
        }
        comparison = self._compare_clarification_value(mode_summaries)

        return {
            "modes": ABLATION_MODES,
            "mode_summaries": mode_summaries,
            "comparison": comparison,
            "passed": comparison["clarification_layer_lift"] > 0,
        }

    def _runner_for_mode(self, mode: str) -> IntentGroundingEvaluationRunner:
        if mode == "full":
            return IntentGroundingEvaluationRunner(case_file=self.case_file)
        if mode == "without_rule_parser":
            return IntentGroundingEvaluationRunner(
                case_file=self.case_file,
                rule_parser=EmptyRuleParser(),
            )
        if mode == "without_graph_router":
            return IntentGroundingEvaluationRunner(
                case_file=self.case_file,
                grounder=RouteDisabledGrounder(),
            )
        if mode == "without_clarification":
            return IntentGroundingEvaluationRunner(
                case_file=self.case_file,
                clarification=ClarificationDisabledEngine(),
            )
        raise ValueError(f"unknown ablation mode: {mode}")

    @staticmethod
    def _compare_clarification_value(mode_summaries: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        full_rate = mode_summaries["full"]["all_expectations_met_rate"]
        without_clarification_rate = mode_summaries["without_clarification"][
            "all_expectations_met_rate"
        ]
        return {
            "full_layer_success_rate": full_rate,
            "without_clarification_layer_success_rate": without_clarification_rate,
            "clarification_layer_lift": full_rate - without_clarification_rate,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run v0.6 intent grounding ablations")
    parser.add_argument("--case-file")
    args = parser.parse_args(argv)
    try:
        report = IntentGroundingAblationRunner(case_file=args.case_file).run_all()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Intent grounding ablation input error: {type(exc).__name__}", file=sys.stderr)
        return 2

    # CLI 只输出摘要和对比，避免把每条 case 的细节刷满终端。
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
