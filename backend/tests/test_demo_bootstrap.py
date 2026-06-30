import shutil
from pathlib import Path

import duckdb

from app.db import demo_bootstrap


ROOT = Path(__file__).resolve().parents[2]


def _copy_database_assets(target_root: Path) -> None:
    database_dir = target_root / "database"
    database_dir.mkdir()
    shutil.copy(ROOT / "database" / "init.sql", database_dir / "init.sql")
    shutil.copy(ROOT / "database" / "seed_data.py", database_dir / "seed_data.py")


def test_initialize_duckdb_demo_database_seeds_empty_volume_once(tmp_path, monkeypatch):
    # CI 会在 PostgreSQL 矩阵设置全局后端；本用例只验证 DuckDB 自举，需显式隔离环境。
    monkeypatch.setattr(demo_bootstrap.settings, "DATABASE_BACKEND", "duckdb")
    monkeypatch.setattr(demo_bootstrap.settings, "DATABASE_URL", "duckdb:///ignored-for-test.duckdb")

    _copy_database_assets(tmp_path)
    data_dir = tmp_path / "data"

    first_result = demo_bootstrap.initialize_duckdb_demo_database(
        base_dir=tmp_path,
        data_dir=data_dir,
        verbose=False,
    )
    second_result = demo_bootstrap.initialize_duckdb_demo_database(
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
