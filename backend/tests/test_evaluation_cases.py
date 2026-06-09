# 评测 case 文件测试
# 这些测试保证 NL2SQL 评测集不是随手写的样例，而是结构稳定、可批量执行的数据集。

from pathlib import Path

import yaml


CASE_FILE = Path(__file__).resolve().parents[1] / "evaluation" / "cases" / "ecommerce_nl2sql_cases.yaml"


def load_cases():
    with CASE_FILE.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)["cases"]


def test_evaluation_case_file_exists():
    """评测 case 文件必须存在"""
    assert CASE_FILE.exists()


def test_evaluation_cases_have_minimum_size():
    """第一版至少提供 30 条 case，覆盖基本业务、安全和修复场景"""
    cases = load_cases()

    assert len(cases) >= 30


def test_evaluation_cases_have_required_fields():
    """每条 case 必须有稳定 id、问题、分类和安全预期"""
    cases = load_cases()

    for case in cases:
        assert case["id"]
        assert case["question"]
        assert case["category"]
        assert case["safety_expected"] in {"safe", "unsafe"}


def test_evaluation_cases_cover_core_categories():
    """评测集必须覆盖聚合、维度拆分、指标、安全和修复类问题"""
    categories = {case["category"] for case in load_cases()}

    assert {"aggregation", "dimension", "metric", "safety", "repair"}.issubset(categories)


def test_evaluation_cases_have_enough_safety_and_repair_cases():
    """安全和修复 case 数量要足够，否则无法支撑面试里的可靠性论证"""
    cases = load_cases()
    safety_cases = [case for case in cases if case["category"] == "safety"]
    repair_cases = [case for case in cases if case["category"] == "repair"]

    assert len(safety_cases) >= 8
    assert len(repair_cases) >= 5


def test_safe_cases_define_expected_tables_or_metrics():
    """安全业务问题至少要声明期望表或期望指标，方便后续做质量检查"""
    cases = load_cases()
    safe_cases = [case for case in cases if case["safety_expected"] == "safe"]

    for case in safe_cases:
        assert case.get("expected_tables") or case.get("expected_metrics")
