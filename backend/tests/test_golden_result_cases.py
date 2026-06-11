# 结果正确性黄金 case 文件测试
# 这些测试先锁定 case 结构与核心业务断言，避免后续评测口径悄然漂移。

from pathlib import Path

import yaml


CASE_FILE = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "cases"
    / "golden_result_cases.yaml"
)


def load_cases():
    # 统一从固定路径加载，确保本地和 CI 使用同一份人工审核基准。
    with CASE_FILE.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)["cases"]


def test_golden_cases_have_exact_core_case_ids():
    """黄金基准必须保持设计约定的 10 条核心分析问题及顺序。"""
    cases = load_cases()

    assert [case["id"] for case in cases] == [
        "monthly_sales_2024",
        "top_products_by_sales",
        "customer_count_by_region",
        "sales_by_region",
        "sales_by_category",
        "refund_rate_by_category",
        "average_order_value_2024",
        "repeat_purchase_rate",
        "payment_method_sales",
        "monthly_order_count",
    ]


def test_each_golden_case_defines_reference_and_comparison():
    """每条 case 都必须声明可执行参考 SQL 和明确比较规则。"""
    for case in load_cases():
        assert case["question"]
        assert case["category"] in {
            "aggregation",
            "time_series",
            "top_n",
            "dimension",
            "business_metric",
        }
        assert case["reference_sql"].strip()
        assert case["comparison"]["mode"] in {
            "unordered",
            "ordered",
            "top_n",
            "scalar",
        }
        assert case["comparison"]["required_columns"]
        assert case["comparison"]["absolute_tolerance"] >= 0


def test_core_business_cases_have_fixed_assertions():
    """关键业务 case 必须用种子数据固定断言长期锁定真实结果。"""
    cases = {case["id"]: case for case in load_cases()}
    required = {
        "monthly_sales_2024",
        "top_products_by_sales",
        "customer_count_by_region",
        "sales_by_category",
        "refund_rate_by_category",
        "average_order_value_2024",
        "repeat_purchase_rate",
        "monthly_order_count",
    }

    assert all(cases[case_id].get("fixed_assertions") for case_id in required)
