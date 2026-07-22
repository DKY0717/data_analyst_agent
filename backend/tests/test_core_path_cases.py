from pathlib import Path

import yaml

from evaluation.core_path import CorePathCaseLoader
from evaluation.permission_evaluator import default_cases as permission_cases


ROOT = Path(__file__).resolve().parents[2]
CORE_CASE_FILE = ROOT / "backend" / "evaluation" / "cases" / "core_path_cases.yaml"
NL2SQL_CASE_FILE = ROOT / "backend" / "evaluation" / "cases" / "ecommerce_nl2sql_cases.yaml"
GOLDEN_CASE_FILE = ROOT / "backend" / "evaluation" / "cases" / "golden_result_cases.yaml"
FRONTEND_AGENT_FILE = ROOT / "frontend" / "src" / "api" / "agent.js"
PREFLIGHT_FILE = ROOT / "scripts" / "interview_demo_preflight.py"


def load_yaml_cases(path: Path) -> list[dict]:
    """复用已有评测 YAML，确保核心路径只引用真实存在的 case。"""
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file)
    return payload["cases"]


def test_core_path_case_file_exists_and_has_minimum_size():
    loader = CorePathCaseLoader(CORE_CASE_FILE)
    cases = loader.load_cases()

    assert CORE_CASE_FILE.exists()
    assert len(cases) >= 12
    assert loader.load_version() == "1.7"


def test_core_path_cases_have_required_fields_and_unique_ids():
    cases = CorePathCaseLoader(CORE_CASE_FILE).load_cases()
    ids = [case.case_id for case in cases]

    assert len(ids) == len(set(ids))
    for case in cases:
        assert case.case_id
        assert case.question
        assert case.category in {
            "business_success",
            "business_metric",
            "follow_up",
            "permission",
            "safety_failure",
            "clarification",
        }
        assert case.expected_surfaces
        assert case.success_criteria
        assert case.expected_status in {
            "completed",
            "blocked",
            "clarification_required",
        }


def test_core_path_cases_cover_demo_categories():
    categories = {case.category for case in CorePathCaseLoader(CORE_CASE_FILE).load_cases()}

    assert {
        "business_success",
        "business_metric",
        "follow_up",
        "permission",
        "safety_failure",
        "clarification",
    }.issubset(categories)


def test_core_path_linked_cases_exist_in_existing_assets():
    cases = CorePathCaseLoader(CORE_CASE_FILE).load_cases()
    nl2sql_ids = {case["id"] for case in load_yaml_cases(NL2SQL_CASE_FILE)}
    golden_ids = {case["id"] for case in load_yaml_cases(GOLDEN_CASE_FILE)}
    permission_ids = {case.case_id for case in permission_cases()}

    for case in cases:
        for link in case.linked_cases:
            if link["source"] == "nl2sql":
                assert link["id"] in nl2sql_ids
            elif link["source"] == "golden_result":
                assert link["id"] in golden_ids
            elif link["source"] == "permission":
                assert link["id"] in permission_ids
            else:
                raise AssertionError(f"unknown linked source: {link['source']}")


def test_core_path_loader_groups_cases_by_category():
    # 分组接口给脚本和文档生成器使用，避免每处重复手写筛选逻辑。
    grouped = CorePathCaseLoader(CORE_CASE_FILE).group_by_category()

    assert grouped["business_success"][0].case_id == "monthly_sales_demo"
    assert grouped["permission"][0].demo_role == "analyst"
    assert grouped["safety_failure"]


def test_frontend_recommended_questions_start_with_core_business_subset():
    frontend = FRONTEND_AGENT_FILE.read_text(encoding="utf-8")
    expected_questions = [
        "统计 2024 年每个月的销售额",
        "找出销售额最高的 5 个商品",
        "统计各商品类别的销售额",
        "分析各商品类别的退款率",
        "计算 2024 年的平均客单价",
        "统计各支付方式对应的销售额",
    ]

    positions = [frontend.index(f"'{question}'") for question in expected_questions]

    assert positions == sorted(positions)


def test_interview_preflight_demo_sequence_matches_core_path_mainline():
    script = PREFLIGHT_FILE.read_text(encoding="utf-8")
    mainline_questions = [
        case.question
        for case in CorePathCaseLoader(CORE_CASE_FILE).load_cases()
        if case.case_id
        in {
            "monthly_sales_demo",
            "category_refund_rate_demo",
            "analyst_row_filter_demo",
            "analyst_customer_name_block_demo",
            "admin_customer_name_demo",
            "dangerous_delete_demo",
        }
    ]

    for question in mainline_questions:
        assert question in script
