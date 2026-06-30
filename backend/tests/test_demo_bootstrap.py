import shutil
from pathlib import Path

import duckdb

from app.db.demo_bootstrap import initialize_duckdb_demo_database


ROOT = Path(__file__).resolve().parents[2]


def _copy_database_assets(target_root: Path) -> None:
    database_dir = target_root / "database"
    database_dir.mkdir()
    shutil.copy(ROOT / "database" / "init.sql", database_dir / "init.sql")
    shutil.copy(ROOT / "database" / "seed_data.py", database_dir / "seed_data.py")


def test_initialize_duckdb_demo_database_seeds_empty_volume_once(tmp_path):
    _copy_database_assets(tmp_path)
    data_dir = tmp_path / "data"

    first_result = initialize_duckdb_demo_database(
        base_dir=tmp_path,
        data_dir=data_dir,
        verbose=False,
    )
    second_result = initialize_duckdb_demo_database(
        base_dir=tmp_path,
        data_dir=data_dir,
        verbose=False,
    )

    connection = duckdb.connect(str(data_dir / "database.duckdb"))
    try:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("regions", "categories", "products", "orders", "refunds")
        }
    finally:
        connection.close()

    assert first_result == "initialized"
    assert second_result == "already_initialized"
    assert counts == {
        "regions": 30,
        "categories": 8,
        "products": 200,
        "orders": 5511,
        "refunds": 718,
    }
