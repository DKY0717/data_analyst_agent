"""固定危险意图 case 的规模和分类契约测试。"""

from collections import Counter
from pathlib import Path

import yaml


CASE_FILE = Path(__file__).parents[1] / "evaluation" / "cases" / "unsafe_intent_cases.yaml"


def test_unsafe_intent_cases_have_required_scale_and_shape():
    cases = yaml.safe_load(CASE_FILE.read_text(encoding="utf-8"))["cases"]

    assert len(cases) >= 35
    assert all(case["id"] and case["question"] and case["category"] for case in cases)
    assert all(isinstance(case["expected_safe"], bool) for case in cases)
    assert len({case["id"] for case in cases}) == len(cases)

    counts = Counter(case["category"] for case in cases)
    minimum_counts = {
        "data_mutation": 8,
        "credential_access": 5,
        "system_access": 5,
        "security_bypass": 4,
        "sensitive_export": 3,
        "safe_analysis": 10,
    }
    assert all(counts[category] >= minimum for category, minimum in minimum_counts.items())

    for case in cases:
        if case["expected_safe"]:
            assert case.get("expected_rule_id") is None
        else:
            assert case["expected_rule_id"]
