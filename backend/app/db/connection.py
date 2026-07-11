# 数据库连接管理模块
# 支持 DuckDB（嵌入式）和 PostgreSQL（生产级）双后端
# 通过 DATABASE_URL 或 DATABASE_BACKEND 环境变量自动选择

from contextlib import contextmanager

from ..config import settings
from ..utils.logger import logger
from ..utils.exceptions import DatabaseError


def detect_backend() -> str:
    """根据 DATABASE_URL 自动检测数据库后端"""
    url = settings.DATABASE_URL
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return "postgresql"
    return "duckdb"


class DatabaseConnection:
    """数据库连接管理器（支持 DuckDB 和 PostgreSQL）"""

    def __init__(self):
        self.backend = settings.DATABASE_BACKEND or detect_backend()
        logger.info(f"数据库后端: {self.backend}")

    def get_connection(self):
        """创建新的数据库连接"""
        try:
            if self.backend == "postgresql":
                return self._get_pg_connection()
            else:
                return self._get_duckdb_connection()
        except Exception as e:
            logger.error("连接数据库失败: %s", type(e).__name__)
            raise DatabaseError("连接数据库失败") from e

    def _get_duckdb_connection(self):
        """DuckDB 连接"""
        import duckdb
        db_path = str(settings.DATA_DIR / "database.duckdb")
        return duckdb.connect(db_path)

    def _get_pg_connection(self):
        """PostgreSQL 连接"""
        import psycopg2
        conn = psycopg2.connect(
            host=settings.PG_HOST,
            port=settings.PG_PORT,
            user=settings.PG_USER,
            password=settings.PG_PASSWORD,
            dbname=settings.PG_DATABASE,
        )
        conn.autocommit = False
        return conn

    @contextmanager
    def get_session(self):
        """获取数据库会话（自动创建和关闭连接）"""
        conn = self.get_connection()
        try:
            yield conn
            if self.backend == "postgresql":
                conn.commit()
        except Exception as e:
            if self.backend == "postgresql":
                conn.rollback()
            logger.error("数据库会话错误: %s", type(e).__name__)
            raise DatabaseError("数据库会话错误") from e
        finally:
            conn.close()


# 全局连接实例
db_connection = DatabaseConnection()


def get_db():
    return db_connection.get_session()
