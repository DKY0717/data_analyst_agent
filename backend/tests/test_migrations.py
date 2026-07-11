"""Alembic 初始迁移与双数据库边界契约测试。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.config import settings


ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = ROOT / "backend" / "alembic.ini"


def test_single_alembic_tree_has_one_initial_revision():
    config = Config(str(ALEMBIC_INI))
    scripts = ScriptDirectory.from_config(config)
    revisions = list(scripts.walk_revisions())

    legacy_tree = ROOT / "backend" / "migrations"
    assert not legacy_tree.exists() or not any(path.is_file() for path in legacy_tree.rglob("*"))
    assert len(revisions) == 1
    assert revisions[0].revision == "20260711_0001"
    assert revisions[0].down_revision is None


def test_initial_revision_covers_all_business_tables(monkeypatch, capsys):
    migration = (
        ROOT
        / "backend"
        / "alembic"
        / "versions"
        / "20260711_0001_initial_schema.py"
    ).read_text(encoding="utf-8")

    for table_name in (
        "regions",
        "customers",
        "categories",
        "products",
        "orders",
        "order_items",
        "payments",
        "refunds",
    ):
        assert f'"{table_name}"' in migration
    assert migration.count("autoincrement=False") == 8

    # 真正调用 Alembic offline runner，证明 revision 能生成 PostgreSQL DDL。
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "postgresql")
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head", sql=True)
    offline_sql = capsys.readouterr().out
    assert "CREATE TABLE regions" in offline_sql
    assert "CREATE TABLE refunds" in offline_sql
    assert "SERIAL" not in offline_sql


def test_duckdb_migration_boundary_is_explicit():
    env_source = (ROOT / "backend" / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "Alembic only manages PostgreSQL" in env_source
    assert "database/init.sql" in env_source
