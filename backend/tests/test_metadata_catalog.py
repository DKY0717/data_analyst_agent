# Metadata Catalog 测试
# Catalog 是意图概念与物理 Schema 之间的统一入口，必须保留稳定候选和结构化 Join 图。

from app.schema_context.metadata_catalog import MetadataCatalog


def test_catalog_indexes_metrics_dimensions_and_join_graph():
    catalog = MetadataCatalog.from_sources()

    assert catalog.metrics["sales_amount"]["candidate_id"] == "sales_by_order_total"
    assert catalog.dimensions["region"]["candidate_id"] == "region_name"
    assert ("orders.customer_id", "customers.customer_id") in catalog.join_edges


def test_catalog_finds_metric_and_dimension_candidates_by_alias():
    catalog = MetadataCatalog.from_sources()

    metrics = catalog.find_metric_candidates("GMV")
    dimensions = catalog.find_dimension_candidates("城市")

    assert metrics[0]["key"] == "sales_amount"
    assert dimensions[0]["key"] == "region"


def test_catalog_returns_isolated_table_schema_copy():
    catalog = MetadataCatalog.from_sources()

    orders = catalog.table_schema("orders")
    orders["columns"].clear()

    assert catalog.table_schema("orders")["columns"]
