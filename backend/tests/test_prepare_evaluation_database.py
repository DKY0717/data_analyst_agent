import duckdb

from scripts.prepare_evaluation_database import prepare_evaluation_database


def test_prepare_evaluation_database_rebuilds_repeatably(tmp_path):
    database_path = tmp_path / "evaluation.duckdb"

    prepare_evaluation_database(database_path)
    prepare_evaluation_database(database_path)

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("regions", "categories", "products", "orders", "refunds")
        }
    finally:
        connection.close()

    assert counts == {
        "regions": 10,
        "categories": 8,
        "products": 40,
        "orders": 304,
        "refunds": 53,
    }
