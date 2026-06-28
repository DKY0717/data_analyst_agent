# pytest 启动时会先加载 conftest.py；这里提前设置测试专用项目根目录，
# 避免测试误用真实 data/database.duckdb，保证不同机器上一键运行结果一致。

import os
import importlib.util
from pathlib import Path

import duckdb


TEST_ROOT = Path(__file__).parent / ".tmp"
REPO_ROOT = Path(__file__).resolve().parents[2]

# 在 app.config 被导入前覆盖 PROJECT_ROOT，让 settings.DATA_DIR / LOG_DIR 指向测试目录。
os.environ["PROJECT_ROOT"] = str(TEST_ROOT)
# 测试环境不需要导出 span，避免异步 ConsoleSpanExporter 在 pytest 关闭捕获后写 stdout。
os.environ["OTEL_EXPORTER"] = "none"


def _prepare_test_database() -> None:
    """创建带固定种子数据的隔离 DuckDB，供确定性集成测试复用。"""
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
        # 动态加载根目录种子脚本，避免测试依赖未跟踪的本地 DuckDB 文件。
        seed_path = REPO_ROOT / "database" / "seed_data.py"
        spec = importlib.util.spec_from_file_location("test_seed_data", seed_path)
        seed_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_module)
        seed_module.seed_database(connection=conn, verbose=False)
    finally:
        conn.close()


_prepare_test_database()
