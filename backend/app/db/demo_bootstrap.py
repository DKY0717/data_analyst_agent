"""Docker 演示库初始化工具。

这个模块只服务 DuckDB 演示/面试部署：容器第一次启动且数据卷为空时，
自动创建业务表并写入固定种子数据，避免 `docker-compose up -d` 后拿到空库。
"""

import importlib.util
from pathlib import Path

import duckdb

from ..config import settings


REQUIRED_BUSINESS_TABLES = (
    "regions",
    "customers",
    "categories",
    "products",
    "orders",
    "order_items",
    "payments",
    "refunds",
)


def _detect_backend() -> str:
    url = settings.DATABASE_URL
    if settings.DATABASE_BACKEND:
        return settings.DATABASE_BACKEND
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return "postgresql"
    return "duckdb"


def _has_seeded_business_data(connection) -> bool:
    """用业务表和 orders 行数判断是否已初始化，避免重启容器时覆盖持久化数据。"""
    existing_tables = {
        row[0]
        for row in connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            """
        ).fetchall()
    }
    if not set(REQUIRED_BUSINESS_TABLES).issubset(existing_tables):
        return False

    return connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] > 0


def _load_seed_module(seed_path: Path):
    spec = importlib.util.spec_from_file_location("docker_demo_seed_data", seed_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载种子脚本: {seed_path}")

    seed_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_module)
    return seed_module


def initialize_duckdb_demo_database(
    base_dir: Path | None = None,
    data_dir: Path | None = None,
    verbose: bool = True,
) -> str:
    """初始化 DuckDB 演示库；返回状态字符串便于测试和启动日志确认。"""
    if _detect_backend() != "duckdb":
        if verbose:
            print("非 DuckDB 后端，跳过演示库自动初始化。")
        return "skipped_non_duckdb"

    base_dir = Path(base_dir or settings.BASE_DIR)
    data_dir = Path(data_dir or settings.DATA_DIR)
    init_sql_path = base_dir / "database" / "init.sql"
    seed_path = base_dir / "database" / "seed_data.py"
    db_path = data_dir / "database.duckdb"

    if not init_sql_path.exists() or not seed_path.exists():
        missing = init_sql_path if not init_sql_path.exists() else seed_path
        raise FileNotFoundError(f"DuckDB 演示库初始化资产不存在: {missing}")

    # 容器数据卷可能是全新的；这里显式建目录，保证第一次启动不依赖宿主机预建路径。
    data_dir.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(db_path))
    try:
        if _has_seeded_business_data(connection):
            if verbose:
                print("DuckDB 演示库已存在，跳过自动初始化。")
            return "already_initialized"

        # 先建表再 seed，复用项目已有固定种子脚本，保证 Docker、CI、本地评测数据一致。
        connection.execute(init_sql_path.read_text(encoding="utf-8"))
        seed_module = _load_seed_module(seed_path)
        seed_module.seed_database(connection=connection, verbose=verbose)
    finally:
        connection.close()

    if verbose:
        print(f"DuckDB 演示库初始化完成: {db_path}")
    return "initialized"


if __name__ == "__main__":
    initialize_duckdb_demo_database()
