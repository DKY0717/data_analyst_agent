"""重建真实评测使用的固定 DuckDB 数据库。"""

from pathlib import Path

import duckdb

from database.seed_data import seed_database


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = ROOT / "data" / "database.duckdb"
INIT_SQL_PATH = ROOT / "database" / "init.sql"


def prepare_evaluation_database(database_path: Path = DEFAULT_DATABASE_PATH) -> Path:
    """重建表结构并写入可复现种子数据。"""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # 真实评测必须从空库开始，避免历史数据影响结果正确率。
    if database_path.exists():
        database_path.unlink()

    init_sql = INIT_SQL_PATH.read_text(encoding="utf-8")
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(init_sql)
        seed_database(connection=connection, verbose=False)
    finally:
        connection.close()

    return database_path


if __name__ == "__main__":
    prepared_path = prepare_evaluation_database()
    print(f"Evaluation database prepared: {prepared_path}")
