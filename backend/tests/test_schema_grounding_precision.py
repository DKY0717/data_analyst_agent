"""Schema Grounding 路由精度回归测试。"""

from app.agents.grounding import SchemaGrounder
from app.analysis_intent.models import AnalysisIntent, IntentSlot


def intent(metric: str, dimension: str | None = None) -> AnalysisIntent:
    dimensions = (
        [IntentSlot(concept=dimension, confidence=0.95, evidence=dimension)]
        if dimension
        else []
    )
    return AnalysisIntent(
        metrics=[IntentSlot(concept=metric, confidence=0.95, evidence=metric)],
        dimensions=dimensions,
        overall_confidence=0.95,
    )


def test_sales_by_region_builds_exact_physical_route():
    grounding = SchemaGrounder().ground(intent("sales_amount", "region"))
    route = grounding["schema_route"]

    assert route["selected_tables"] == ["customers", "orders", "regions"]
    assert route["join_edges"] == [
        ("orders.customer_id", "customers.customer_id"),
        ("customers.region_id", "regions.region_id"),
    ]
    assert all("(" not in table for table in route["selected_tables"])


def test_category_override_selects_item_amount_route_without_pseudo_tables():
    grounding = SchemaGrounder().ground(intent("sales_amount", "category"))
    route = grounding["schema_route"]
    metric_candidates = grounding["metric_groundings"][0]["candidates"]

    assert route["selected_tables"] == ["categories", "order_items", "orders", "products"]
    assert route["join_edges"] == [
        ("orders.order_id", "order_items.order_id"),
        ("order_items.product_id", "products.product_id"),
        ("products.category_id", "categories.category_id"),
    ]
    assert max(metric_candidates, key=lambda item: item["score"])["candidate_id"] == "sales_by_item_amount"


def test_refund_rate_category_route_combines_metric_and_dimension_paths():
    route = SchemaGrounder().ground(intent("refund_rate", "category"))["schema_route"]

    assert route["selected_tables"] == [
        "categories",
        "order_items",
        "orders",
        "products",
        "refunds",
    ]
    assert ("orders.order_id", "refunds.order_id") in route["join_edges"]
    assert ("products.category_id", "categories.category_id") in route["join_edges"]


def test_repeat_purchase_metric_does_not_expose_derived_cte_as_physical_table():
    grounding = SchemaGrounder().ground(intent("repeat_purchase_rate"))
    route = grounding["schema_route"]
    candidate = grounding["metric_groundings"][0]["candidates"][0]

    assert route["selected_tables"] == ["orders"]
    assert "customer_order_stats" not in candidate["tables"]
    assert all(not column.startswith("customer_order_stats.") for column in candidate["columns"])
