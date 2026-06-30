import importlib.util
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "database" / "seed_data.py"
SPEC = importlib.util.spec_from_file_location("seed_data", SEED_PATH)
seed_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seed_data)


def test_seed_database_can_run_twice_on_existing_schema(tmp_path):
    db_path = tmp_path / "repeatable.duckdb"
    init_sql = (ROOT / "database" / "init.sql").read_text(encoding="utf-8")

    connection = duckdb.connect(str(db_path))
    try:
        connection.execute(init_sql)

        # 种子脚本常被本地演示重复运行；重复执行应该重建固定数据，而不是主键冲突。
        seed_data.seed_database(connection=connection, verbose=False)
        seed_data.seed_database(connection=connection, verbose=False)

        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("regions", "categories", "products", "orders", "refunds")
        }
    finally:
        connection.close()

    assert counts == {
        "regions": 30,
        "categories": 8,
        "products": 200,
        "orders": 5511,
        "refunds": 718,
    }
