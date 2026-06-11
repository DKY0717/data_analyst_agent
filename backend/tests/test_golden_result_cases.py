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

EXPECTED_CASE_CONTRACTS = {
    "monthly_sales_2024": {
        "category": "time_series",
        "mode": "ordered",
        "required_columns": ["month", "sales_amount"],
        "order_by": ["month"],
    },
    "top_products_by_sales": {
        "category": "top_n",
        "mode": "top_n",
        "required_columns": ["product_name", "sales_amount"],
        "order_by": ["sales_amount", "product_name"],
    },
    "customer_count_by_region": {
        "category": "dimension",
        "mode": "unordered",
        "required_columns": ["region_name", "customer_count"],
    },
    "sales_by_region": {
        "category": "dimension",
        "mode": "unordered",
        "required_columns": ["region_name", "sales_amount"],
    },
    "sales_by_category": {
        "category": "aggregation",
        "mode": "unordered",
        "required_columns": ["category_name", "sales_amount"],
    },
    "refund_rate_by_category": {
        "category": "business_metric",
        "mode": "unordered",
        "required_columns": ["category_name", "refund_rate"],
    },
    "average_order_value_2024": {
        "category": "business_metric",
        "mode": "scalar",
        "required_columns": ["average_order_value"],
    },
    "repeat_purchase_rate": {
        "category": "business_metric",
        "mode": "scalar",
        "required_columns": ["repeat_purchase_rate"],
    },
    "payment_method_sales": {
        "category": "dimension",
        "mode": "unordered",
        "required_columns": ["payment_method", "sales_amount"],
    },
    "monthly_order_count": {
        "category": "time_series",
        "mode": "ordered",
        "required_columns": ["month", "order_count"],
        "order_by": ["month"],
    },
}

EXPECTED_FIXED_ASSERTIONS = {
    "monthly_sales_2024": {"row_count": 12},
    "top_products_by_sales": {"row_count": 5},
    "customer_count_by_region": {
        "row_count": 5,
        "sum_column": {"column": "customer_count", "value": 100},
    },
    "sales_by_category": {"row_count": 8},
    "refund_rate_by_category": {"row_count": 8},
    "average_order_value_2024": {
        "scalar": {
            "column": "average_order_value",
            "value": 1956.7938144329896,
            "absolute_tolerance": 0.001,
        }
    },
    "repeat_purchase_rate": {
        "scalar": {
            "column": "repeat_purchase_rate",
            "value": 0.76,
            "absolute_tolerance": 0.001,
        }
    },
    "monthly_order_count": {
        "row_count": 36,
        "sum_column": {"column": "order_count", "value": 304},
    },
}

EXPECTED_SQL_FRAGMENTS = {
    "monthly_sales_2024": ["extract(year from order_date) = 2024", "sum(total_amount)"],
    "top_products_by_sales": ["sum(oi.quantity * oi.unit_price)", "limit 5"],
    "sales_by_region": ["extract(year from o.order_date) = 2024", "sum(o.total_amount)"],
    "sales_by_category": ["sum(oi.quantity * oi.unit_price)"],
    "refund_rate_by_category": [
        "count(distinct r.refund_id)",
        "count(distinct o.order_id)",
        "left join refunds",
    ],
    "average_order_value_2024": [
        "extract(year from order_date) = 2024",
        "sum(total_amount)",
    ],
    "repeat_purchase_rate": ["count(distinct order_id)", "order_count > 1"],
}


def load_cases():
    # 统一从固定路径加载，确保本地和 CI 使用同一份人工审核基准。
    with CASE_FILE.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)["cases"]


def load_cases_by_id():
    """按稳定 ID 建立索引，让契约断言集中表达且容易定位失败 case。"""
    return {case["id"]: case for case in load_cases()}


def normalize_sql(sql):
    """只归一化大小写和空白，既锁定业务口径又允许 SQL 排版调整。"""
    return " ".join(sql.lower().split())


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


def test_each_golden_case_matches_exact_comparison_contract():
    """锁定每条 case 的类别、比较模式、列结构、排序字段和统一容差。"""
    cases = load_cases_by_id()

    for case_id, expected in EXPECTED_CASE_CONTRACTS.items():
        case = cases[case_id]
        comparison = case["comparison"]

        assert case["category"] == expected["category"], case_id
        assert comparison["mode"] == expected["mode"], case_id
        assert comparison["required_columns"] == expected["required_columns"], case_id
        assert comparison.get("order_by") == expected.get("order_by"), case_id
        assert comparison["absolute_tolerance"] == 0.001, case_id


def test_core_business_cases_match_exact_fixed_assertions():
    """固定断言必须锁定种子库真实值，不能只检查字段是否存在。"""
    cases = load_cases_by_id()

    for case_id, expected in EXPECTED_FIXED_ASSERTIONS.items():
        assert cases[case_id]["fixed_assertions"] == expected, case_id


def test_reference_sql_preserves_key_business_definitions():
    """关键 SQL 片段用于防止时间范围、金额来源和业务指标口径漂移。"""
    cases = load_cases_by_id()

    for case_id, expected_fragments in EXPECTED_SQL_FRAGMENTS.items():
        normalized_sql = normalize_sql(cases[case_id]["reference_sql"])

        for fragment in expected_fragments:
            assert fragment in normalized_sql, f"{case_id}: missing {fragment}"
