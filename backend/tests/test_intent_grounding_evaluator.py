"""v0.6 分层意图与 Grounding 评测器测试。"""

from evaluation.intent_grounding_evaluator import IntentGroundingEvaluationRunner, main


def test_load_cases_contains_v06_contract_fields():
    cases = IntentGroundingEvaluationRunner().load_cases()

    assert len(cases) >= 7
    first = cases[0]
    assert {"id", "question", "expected_metrics", "expected_candidate_ids"} <= set(first)


def test_evaluate_case_checks_slots_grounding_route_and_clarification():
    runner = IntentGroundingEvaluationRunner()
    case = {
        "id": "sales_by_region_2024",
        "question": "按地区统计 2024 年销售额",
        "category": "metric_dimension_filter",
        "expected_metrics": ["sales_amount"],
        "expected_dimensions": ["region"],
        "expected_filters": [
            {"concept": "order_date", "operator": "year_equals", "value": 2024}
        ],
        "expected_candidate_ids": ["sales_by_order_total", "region_name"],
        "expected_route_tables": ["orders", "customers", "regions"],
        "expected_clarification_required": False,
    }

    result = runner.evaluate_case(case)

    assert result["metrics_matched"] is True
    assert result["dimensions_matched"] is True
    assert result["filters_matched"] is True
    assert result["grounding_candidates_matched"] is True
    assert result["route_tables_matched"] is True
    assert result["clarification_decision_matched"] is True
    assert result["passed"] is True


def test_vague_case_requires_metric_clarification_options():
    runner = IntentGroundingEvaluationRunner()
    case = {
        "id": "vague_analysis_requires_metric_clarification",
        "question": "帮我分析一下",
        "category": "clarification",
        "expected_metrics": [],
        "expected_dimensions": [],
        "expected_candidate_ids": [],
        "expected_route_tables": [],
        "expected_clarification_required": True,
        "expected_clarification_option_ids": [
            "metric_sales_amount",
            "metric_order_count",
            "metric_customer_count",
        ],
    }

    result = runner.evaluate_case(case)

    assert result["clarification_required"] is True
    assert result["clarification_options_matched"] is True
    assert result["passed"] is True


def test_summary_reports_all_layer_metrics():
    runner = IntentGroundingEvaluationRunner()
    report = runner.evaluate_all()
    summary = report["summary"]

    assert summary["total_cases"] >= 7
    assert summary["slot_match_rate"] == 1.0
    assert summary["grounding_candidate_hit_rate"] == 1.0
    assert summary["route_table_recall_rate"] == 1.0
    assert summary["clarification_decision_accuracy"] == 1.0
    assert summary["all_expectations_met_rate"] == 1.0
    assert summary["passed"] is True


def test_main_writes_reports_and_returns_zero(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EVALUATION_REPORT_DIR", str(tmp_path))

    assert main([]) == 0
    output = capsys.readouterr().out
    assert '"passed": true' in output
    assert "Intent grounding evaluation report:" in output
    assert list(tmp_path.glob("intent-grounding-evaluation-*.md"))
    assert list(tmp_path.glob("intent-grounding-evaluation-*.json"))


def test_main_returns_two_for_missing_case_file(tmp_path, capsys):
    assert main(["--case-file", str(tmp_path / "missing.yaml")]) == 2
    assert "Intent grounding evaluation input error" in capsys.readouterr().err
