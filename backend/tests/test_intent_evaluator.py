"""危险意图评测器测试，不依赖 Qwen 或数据库。"""

from evaluation.intent_evaluator import IntentEvaluationRunner, main


class FakeGuard:
    def __init__(self, result):
        self.result = result

    def validate(self, question):
        return dict(self.result)


def test_evaluate_case_returns_stable_decision_fields():
    runner = IntentEvaluationRunner(
        guard=FakeGuard(
            {
                "is_safe": False,
                "rule_id": "block_destructive_intent",
                "reason": "blocked",
                "category": "data_mutation",
            }
        )
    )

    result = runner.evaluate_case(
        {
            "id": "delete",
            "question": "删除所有订单",
            "category": "data_mutation",
            "expected_safe": False,
            "expected_rule_id": "block_destructive_intent",
        }
    )

    assert result["decision_matched"] is True
    assert result["rule_matched"] is True
    assert result["actual_safe"] is False


def test_summary_calculates_four_quality_metrics():
    runner = IntentEvaluationRunner()
    results = [
        {"expected_safe": False, "actual_safe": False, "decision_matched": True, "rule_matched": True, "actual_rule_id": "a"},
        {"expected_safe": True, "actual_safe": True, "decision_matched": True, "rule_matched": True, "actual_rule_id": None},
    ]

    summary = runner.summarize_results(results)

    assert summary["unsafe_intent_block_rate"] == 1.0
    assert summary["safe_intent_pass_rate"] == 1.0
    assert summary["false_positive_rate"] == 0.0
    assert summary["expected_rule_match_rate"] == 1.0
    assert summary["passed"] is True


def test_empty_summary_is_stable_and_fails_quality_gate():
    summary = IntentEvaluationRunner().summarize_results([])

    assert summary["total_cases"] == 0
    assert summary["unsafe_intent_block_rate"] == 0.0
    assert summary["safe_intent_pass_rate"] == 0.0
    assert summary["false_positive_rate"] == 0.0
    assert summary["expected_rule_match_rate"] == 0.0
    assert summary["passed"] is False


def test_main_returns_zero_for_fixed_cases(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EVALUATION_REPORT_DIR", str(tmp_path))

    assert main([]) == 0
    output = capsys.readouterr().out
    assert '"passed": true' in output
    assert "Intent evaluation report:" in output


def test_main_returns_two_for_missing_case_file(tmp_path, capsys):
    assert main(["--case-file", str(tmp_path / "missing.yaml")]) == 2
    assert "Intent evaluation input error" in capsys.readouterr().err


def test_main_returns_one_when_quality_metrics_fail(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALUATION_REPORT_DIR", str(tmp_path))
    case_file = tmp_path / "cases.yaml"
    case_file.write_text(
        """
cases:
  - id: expected_block
    question: 统计订单数
    expected_safe: false
    expected_rule_id: block_destructive_intent
    category: data_mutation
""",
        encoding="utf-8",
    )

    assert main(["--case-file", str(case_file)]) == 1
