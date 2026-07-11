"""PostgreSQL Alembic 环境；DuckDB 演示库通过 init.sql 可重建。"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

config = context.config

if (
    config.config_file_name is not None
    and config.attributes.get("configure_logger", True)
):
    # CLI 默认沿用 Alembic 日志配置；进程内调用可关闭重配置，避免破坏宿主的日志处理器。
    fileConfig(config.config_file_name)

target_metadata = None

backend = settings.DATABASE_BACKEND or (
    "postgresql" if settings.DATABASE_URL.startswith("postgresql") else "duckdb"
)
if backend != "postgresql":
    raise RuntimeError(
        "Alembic only manages PostgreSQL; rebuild DuckDB from database/init.sql"
    )

db_url = (
    f"postgresql+psycopg2://{quote_plus(settings.PG_USER)}:"
    f"{quote_plus(settings.PG_PASSWORD)}@{settings.PG_HOST}:{settings.PG_PORT}/"
    f"{quote_plus(settings.PG_DATABASE)}"
)

# ConfigParser 把 % 当插值符；URL 编码后的百分号需转义后再写入配置。
config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
