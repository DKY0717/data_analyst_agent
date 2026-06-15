import importlib.util
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "prepare_evaluation_database.py"
SPEC = importlib.util.spec_from_file_location("prepare_evaluation_database", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
prepare_evaluation_database = MODULE.prepare_evaluation_database


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
