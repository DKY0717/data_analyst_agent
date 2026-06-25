"""v0.6 分层意图/Grounding 消融实验测试。"""

from evaluation.ablation_runner import ABLATION_MODES, IntentGroundingAblationRunner, main


def test_ablation_modes_are_stable():
    assert ABLATION_MODES == (
        "full",
        "without_rule_parser",
        "without_graph_router",
        "without_clarification",
    )


def test_ablation_runner_reports_same_metrics_for_each_mode():
    report = IntentGroundingAblationRunner().run_all()

    assert set(report["mode_summaries"]) == set(ABLATION_MODES)
    for summary in report["mode_summaries"].values():
        assert summary["total_cases"] >= 7
        assert "slot_match_rate" in summary
        assert "grounding_candidate_hit_rate" in summary
        assert "route_table_recall_rate" in summary
        assert "clarification_decision_accuracy" in summary
        assert "all_expectations_met_rate" in summary


def test_without_clarification_quantifies_active_clarification_value():
    report = IntentGroundingAblationRunner().run_all()
    comparison = report["comparison"]

    assert comparison["full_layer_success_rate"] == 1.0
    assert comparison["without_clarification_layer_success_rate"] < 1.0
    assert comparison["clarification_layer_lift"] > 0
    assert report["passed"] is True


def test_main_prints_comparison_and_returns_zero(capsys):
    assert main([]) == 0

    output = capsys.readouterr().out
    assert '"without_clarification_layer_success_rate"' in output
    assert '"passed": true' in output
