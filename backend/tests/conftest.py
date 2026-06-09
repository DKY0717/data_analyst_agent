# pytest 启动时会先加载 conftest.py；这里提前设置测试专用项目根目录，
# 避免测试误用真实 data/database.duckdb，保证不同机器上一键运行结果一致。

import os
from pathlib import Path

import duckdb


TEST_ROOT = Path(__file__).parent / ".tmp"
REPO_ROOT = Path(__file__).resolve().parents[2]

# 在 app.config 被导入前覆盖 PROJECT_ROOT，让 settings.DATA_DIR / LOG_DIR 指向测试目录。
os.environ["PROJECT_ROOT"] = str(TEST_ROOT)


def _prepare_test_database() -> None:
    """创建隔离的 DuckDB 测试库，只初始化表结构，不依赖真实业务数据文件。"""
    data_dir = TEST_ROOT / "data"
    log_dir = TEST_ROOT / "logs"
    db_path = data_dir / "database.duckdb"

    # 测试库每次重建，避免上一次运行留下的表或数据影响本次断言。
    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    init_sql = (REPO_ROOT / "database" / "init.sql").read_text(encoding="utf-8")
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(init_sql)
    finally:
        conn.close()


_prepare_test_database()
